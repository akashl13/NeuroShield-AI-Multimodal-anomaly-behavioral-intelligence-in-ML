from __future__ import annotations

from html import escape

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton, QTextEdit, QVBoxLayout
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from database.connection import SessionLocal
from database.models import Alert, BehaviorEvent, Investigation
from gui.theme import APP_STYLE
from ml.explainability import explain_event
from services.alert_service import save_investigation
from services.event_service import baseline_for_user


class InvestigationDialog(QDialog):
    def __init__(self, alert_id: int, analyst, parent=None):
        super().__init__(parent)
        self.alert_id = alert_id
        self.analyst = analyst
        self.setWindowTitle("Alert investigation")
        self.setMinimumSize(620, 650)
        self.setStyleSheet(APP_STYLE)
        root = QVBoxLayout(self)
        self.title = QLabel("Investigation")
        self.title.setObjectName("pageTitle")
        root.addWidget(self.title)
        self.details = QLabel()
        self.details.setWordWrap(True)
        self.details.setStyleSheet("background:white;border:1px solid #e1e7e9;border-radius:4px;padding:14px;line-height:1.5")
        root.addWidget(self.details)
        self.score_label = QLabel()
        self.score_label.setStyleSheet("font-size:16px;font-weight:700")
        root.addWidget(self.score_label)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        root.addWidget(self.progress)
        root.addWidget(QLabel("Contributing factors"))
        self.factors = QVBoxLayout()
        root.addLayout(self.factors)
        self.baseline = QLabel()
        self.baseline.setWordWrap(True)
        self.baseline.setObjectName("muted")
        root.addWidget(self.baseline)
        root.addWidget(QLabel("Analyst notes"))
        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Record findings, context, and follow-up actions…")
        self.notes.setMaximumHeight(130)
        root.addWidget(self.notes)
        actions = QHBoxLayout()
        self.review_button = QPushButton("Mark reviewed")
        self.review_button.setObjectName("secondary")
        self.review_button.clicked.connect(lambda: self._save(False, close=False))
        resolve = QPushButton("Resolve alert")
        resolve.clicked.connect(lambda: self._save(True, close=True))
        close = QPushButton("Close")
        close.setObjectName("secondary")
        close.clicked.connect(self.reject)
        actions.addWidget(self.review_button)
        actions.addStretch(1)
        actions.addWidget(close)
        actions.addWidget(resolve)
        root.addLayout(actions)
        self._load()

    def _load(self) -> None:
        session = SessionLocal()
        try:
            alert = session.scalar(select(Alert).options(
                joinedload(Alert.event).joinedload(BehaviorEvent.device),
                joinedload(Alert.event).joinedload(BehaviorEvent.risk_score),
                joinedload(Alert.event).joinedload(BehaviorEvent.anomaly),
                joinedload(Alert.event).joinedload(BehaviorEvent.prediction),
            ).where(Alert.id == self.alert_id))
            if alert is None:
                raise ValueError("This alert no longer exists.")
            event = alert.event
            risk = event.risk_score
            score = risk.score if risk else 0
            self.title.setText(f"{alert.severity} · {alert.title}")
            self.score_label.setText(f"Risk score  {score} / 100     ·     {risk.level if risk else 'LOW'}")
            self.progress.setValue(score)
            self.details.setText(
                f"<b>Analyst:</b> {escape(self.analyst.username)} &nbsp; <b>Event user:</b> {escape(event.user.username)}<br>"
                f"<b>Device:</b> {escape(event.device.device_id)} &nbsp; <b>IP:</b> {escape(event.ip_address)}<br>"
                f"<b>Timestamp:</b> {event.timestamp.strftime('%Y-%m-%d %H:%M UTC')} &nbsp; <b>Network:</b> {escape(event.network_zone)}<br>"
                f"<b>Session:</b> {event.session_duration_minutes:.0f} min &nbsp; <b>Files:</b> {event.files_accessed} &nbsp; <b>Actions:</b> {event.action_count}<br>"
                f"<b>Failed logins:</b> {event.failed_login_attempts} &nbsp; <b>Detection:</b> {'Anomalous' if event.anomaly and event.anomaly.detected else 'Normal'}"
            )
            factors = risk.factors if risk else {}
            for label, points in sorted(factors.items(), key=lambda item: item[1], reverse=True):
                row = QHBoxLayout()
                name = QLabel(f"{label}  +{points}")
                bar = QProgressBar()
                bar.setRange(0, 25)
                bar.setValue(min(25, points))
                bar.setFormat("")
                row.addWidget(name, 3)
                row.addWidget(bar, 2)
                self.factors.addLayout(row)
            baseline = baseline_for_user(session, event.user_id)
            features = {key: getattr(event, key) for key in (
                "login_hour", "session_duration_minutes", "files_accessed", "action_count", "failed_login_attempts",
                "network_bytes_mb", "cpu_percent", "network_zone", "location_category", "application_usage", "device_was_known",
            )}
            shap_values = explain_event(features, event.anomaly.score if event.anomaly else 0, baseline)["shap_values"]
            if shap_values:
                self.factors.addWidget(QLabel("Classifier feature attribution · SHAP"))
                largest = max(abs(value) for value in shap_values.values()) or 1
                for label, value in sorted(shap_values.items(), key=lambda item: abs(item[1]), reverse=True)[:6]:
                    row = QHBoxLayout()
                    row.addWidget(QLabel(f"{label}  {value:+.3f}"), 3)
                    bar = QProgressBar()
                    bar.setRange(0, 100)
                    bar.setValue(int(abs(value) / largest * 100))
                    bar.setFormat("")
                    row.addWidget(bar, 2)
                    self.factors.addLayout(row)
            else:
                self.factors.addWidget(QLabel("Explainability unavailable for this prediction."))
            self.baseline.setText(
                f"User baseline: typical login {baseline['mean_login_hour']:.1f}:00 · session {baseline['mean_session_minutes']:.0f} min · "
                f"files {baseline['mean_files_accessed']:.1f} · actions {baseline['mean_action_count']:.0f} · "
                f"apps {', '.join(baseline.get('usual_applications', [])) or 'not established'}. "
                f"Isolation Forest score: {event.anomaly.score if event.anomaly else 0:.1f}/100. "
                f"Classifier: {event.prediction.classification if event.prediction else 'not available'} "
                f"({event.prediction.confidence if event.prediction else 0:.0%} confidence)."
            )
            investigation = session.scalar(select(Investigation).where(Investigation.alert_id == alert.id))
            if investigation:
                self.notes.setPlainText(investigation.notes)
                self.review_button.setText("Update review")
            if alert.status == "resolved":
                self.review_button.setDisabled(True)
        except Exception as exc:
            QMessageBox.critical(self, "Investigation unavailable", str(exc))
            self.reject()
        finally:
            session.close()

    def _save(self, resolve: bool, close: bool) -> None:
        session = SessionLocal()
        try:
            alert = session.get(Alert, self.alert_id)
            if alert is None:
                raise ValueError("This alert no longer exists.")
            save_investigation(session, alert, self.analyst.id, self.notes.toPlainText(), resolve)
            if close:
                self.accept()
            else:
                QMessageBox.information(self, "Review saved", "Investigation notes have been saved.")
        except Exception as exc:
            session.rollback()
            QMessageBox.critical(self, "Save failed", str(exc))
        finally:
            session.close()