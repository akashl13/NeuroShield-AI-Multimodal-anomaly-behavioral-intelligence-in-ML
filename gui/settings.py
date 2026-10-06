from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QPushButton, QWidget

from config.settings import DATABASE_URL, DATA_DIR, MODEL_DIR
from data.generate_synthetic import generate_dataset
from gui.widgets import page_header, vertical
from ml.train import train_models


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
        self.database_label = QLabel()
        self.database_label.setStyleSheet("background:white;border:1px solid #e1e7e9;padding:13px;border-radius:4px")
        self.layout.addWidget(QLabel("DATABASE"))
        self.layout.addWidget(self.database_label)
        self.layout.addWidget(QLabel("MODEL TRAINING"))
        self.model_label = QLabel(f"Artifacts: {MODEL_DIR}\nEvaluation report: {MODEL_DIR.parent / 'model_evaluation_report.md'}")
        self.model_label.setStyleSheet("background:white;border:1px solid #e1e7e9;padding:13px;border-radius:4px")
        self.layout.addWidget(self.model_label)
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
        backend = "Neon/PostgreSQL" if DATABASE_URL.startswith(("postgresql", "postgres")) else "Local SQLite"
        self.database_label.setText(f"Backend: {backend}\nConfigured URL: {self._redact_url(DATABASE_URL)}")

    @staticmethod
    def _redact_url(url: str) -> str:
        if "@" not in url:
            return url
        prefix, host = url.rsplit("@", 1)
        scheme, credentials = prefix.split("://", 1)
        user = credentials.split(":", 1)[0]
        return f"{scheme}://{user}:********@{host}"

    def generate_data(self) -> None:
        try:
            frame = generate_dataset()
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            frame.to_csv(DATA_DIR / "synthetic_behavior_data.csv", index=False)
            self.status.setText(f"Generated {len(frame):,} synthetic events at {DATA_DIR / 'synthetic_behavior_data.csv'}.")
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

    def _training_failed(self, error: str) -> None:
        self.train_button.setDisabled(False)
        self.status.setText("Model training failed.")
        QMessageBox.critical(self, "Training failed", error)