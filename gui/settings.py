from __future__ import annotations

import importlib.util
import logging

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QWidget
from sqlalchemy import func, select, text

from config.settings import DATABASE_URL, DATA_DIR, MODEL_DIR
from data.generate_synthetic import generate_dataset
from database.connection import SessionLocal, engine
from database.models import ModelMetric
from gui.widgets import page_header, vertical
from ml.train import train_models

logger = logging.getLogger(__name__)


class TrainingWorker(QThread):
    finished_with_result = Signal(str)
    failed = Signal(str)

    def run(self) -> None:
        try:
            metrics = train_models(DATA_DIR / "synthetic_behavior_data.csv")
            self.finished_with_result.emit(", ".join(f"{name}: F1 {values['f1']:.3f}" for name, values in metrics.items()))
        except Exception as exc:
            self.failed.emit(str(exc))


class SettingsPage(QWidget):
    def __init__(self, analytics_page):
        super().__init__()
        self.analytics_page = analytics_page
        self.worker = None
        self.layout = vertical(self)
        self.layout.addLayout(page_header("System settings", "Manage local synthetic data, model artifacts, and persistence configuration."))
        self.layout.addWidget(QLabel("SYSTEM HEALTH"))
        self.health_label = QLabel("Health status is checked when this page opens.")
        self.health_label.setWordWrap(True)
        self.health_label.setStyleSheet("background:white;border:1px solid #e1e7e9;padding:13px;border-radius:4px;line-height:1.6")
        self.layout.addWidget(self.health_label)
        self.layout.addWidget(QLabel("MODEL TRAINING"))
        self.model_label = QLabel(f"Artifacts: {MODEL_DIR}\nEvaluation report: {MODEL_DIR.parent / 'model_evaluation_report.md'}")
        self.model_label.setStyleSheet("background:white;border:1px solid #e1e7e9;padding:13px;border-radius:4px")
        self.layout.addWidget(self.model_label)
        generator_controls = QHBoxLayout()
        self.dataset_size = QComboBox()
        for rows in (100, 500, 1_000, 5_000, 10_000):
            self.dataset_size.addItem(f"{rows:,} events", rows)
        self.dataset_size.setCurrentIndex(2)
        self.dataset_profile = QComboBox()
        for profile in ("NORMAL", "SUSPICIOUS", "MIXED"):
            self.dataset_profile.addItem(profile.title(), profile)
        generator_controls.addWidget(QLabel("Dataset size"))
        generator_controls.addWidget(self.dataset_size)
        generator_controls.addWidget(QLabel("Behavior profile"))
        generator_controls.addWidget(self.dataset_profile)
        generator_controls.addStretch(1)
        self.layout.addLayout(generator_controls)
        actions = QHBoxLayout()
        generate = QPushButton("Generate synthetic dataset")
        generate.clicked.connect(self.generate_data)
        self.train_button = QPushButton("Train and compare models")
        self.train_button.clicked.connect(self.train)
        actions.addWidget(generate)
        actions.addWidget(self.train_button)
        actions.addStretch(1)
        self.layout.addLayout(actions)
        self.status = QLabel("Synthetic records use reserved documentation IP ranges; no real personal data is included.")
        self.status.setObjectName("muted")
        self.layout.addWidget(self.status)
        self.layout.addStretch(1)

    def refresh(self) -> None:
        database_type = "PostgreSQL" if DATABASE_URL.startswith(("postgresql", "postgres")) else "SQLite"
        database_status = "DISCONNECTED"
        last_training = "No training record"
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            database_status = "CONNECTED"
            session = SessionLocal()
            try:
                trained_at = session.scalar(select(func.max(ModelMetric.trained_at)))
                if trained_at is not None:
                    last_training = trained_at.strftime("%Y-%m-%d %H:%M UTC")
            finally:
                session.close()
        except Exception:
            logger.exception("System health check could not query the configured database")

        model_names = ("isolation_forest", "logistic_regression", "random_forest", "xgboost")
        ready_models = [name for name in model_names if (MODEL_DIR / f"{name}.joblib").is_file()]
        ml_ready = all(importlib.util.find_spec(name) is not None for name in ("sklearn", "xgboost"))
        dataset_status = "AVAILABLE" if (DATA_DIR / "synthetic_behavior_data.csv").is_file() else "NOT AVAILABLE"
        model_status = f"{len(ready_models)}/{len(model_names)} READY"
        self.health_label.setText(
            f"Database: {database_status}\n"
            f"Database type: {database_type}\n"
            f"ML engine: {'READY' if ml_ready else 'NOT READY'}\n"
            f"Models: {model_status}\n"
            f"Synthetic dataset: {dataset_status}\n"
            f"Last training: {last_training}"
        )

    def generate_data(self) -> None:
        try:
            rows = int(self.dataset_size.currentData())
            profile = str(self.dataset_profile.currentData())
            frame = generate_dataset(rows=rows, profile=profile)
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            frame.to_csv(DATA_DIR / "synthetic_behavior_data.csv", index=False)
            anomaly_count = int(frame["is_anomaly"].sum())
            self.status.setText(
                f"Generated {len(frame):,} {profile.lower()} events ({anomaly_count:,} anomalous). "
                f"Training requires both normal and anomalous records."
            )
        except Exception as exc:
            QMessageBox.critical(self, "Dataset generation failed", str(exc))

    def train(self) -> None:
        data_path = DATA_DIR / "synthetic_behavior_data.csv"
        if not data_path.exists():
            self.generate_data()
        self.train_button.setDisabled(True)
        self.status.setText("Training models… this may take a few moments.")
        self.worker = TrainingWorker(self)
        self.worker.finished_with_result.connect(self._training_finished)
        self.worker.failed.connect(self._training_failed)
        self.worker.start()

    def _training_finished(self, result: str) -> None:
        self.train_button.setDisabled(False)
        self.status.setText(f"Training complete. {result}")
        self.analytics_page.refresh()
        self.refresh()

    def _training_failed(self, error: str) -> None:
        self.train_button.setDisabled(False)
        self.status.setText("Model training failed.")
        QMessageBox.critical(self, "Training failed", error)