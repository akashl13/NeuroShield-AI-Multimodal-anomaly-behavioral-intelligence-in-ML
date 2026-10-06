from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QWidget
from sqlalchemy import desc, select
from sqlalchemy.orm import joinedload

from database.connection import SessionLocal
from database.models import BehaviorEvent, User
from gui.widgets import make_table, page_header, set_cell, vertical
from services.event_service import import_csv_events, record_event
from services.simulation_service import generate_behavior_event


class CSVImportWorker(QThread):
    completed = Signal(int)
    failed = Signal(str)

    def __init__(self, filename: str, user_id: int, parent=None):
        super().__init__(parent)
        self.filename = filename
        self.user_id = user_id

    def run(self) -> None:
        session = SessionLocal()
        try:
            user = session.get(User, self.user_id)
            if user is None:
                raise ValueError("The signed-in account is no longer available.")
            self.completed.emit(import_csv_events(session, user, self.filename))
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            session.close()


class EventsPage(QWidget):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.layout = vertical(self)
        self.layout.addLayout(page_header("Behavior events", "Generate synthetic activity or import an anonymized CSV into the analysis pipeline."))
        controls = QHBoxLayout()
        normal = QPushButton("Generate normal event")
        normal.clicked.connect(lambda: self.generate(False))
        suspicious = QPushButton("Generate suspicious event")
        suspicious.setObjectName("danger")
        suspicious.clicked.connect(lambda: self.generate(True))
        self.import_button = QPushButton("Import CSV")
        self.import_button.setObjectName("secondary")
        self.import_button.clicked.connect(self.import_csv)
        controls.addWidget(normal)
        controls.addWidget(suspicious)
        controls.addStretch(1)
        controls.addWidget(self.import_button)
        self.layout.addLayout(controls)
        self.import_status = QLabel("CSV imports are anonymized and limited to 10,000 events per file.")
        self.import_status.setObjectName("muted")
        self.layout.addWidget(self.import_status)
        self.table = make_table(["Time", "Device", "Login", "Files", "Actions", "Failed", "Risk", "Detection"])
        self.layout.addWidget(self.table, 1)
        self.refresh()

    def generate(self, suspicious: bool) -> None:
        session = SessionLocal()
        try:
            result = record_event(session, self.user, generate_behavior_event(self.user.username, suspicious))
            score = result["risk"].score
            self.refresh()
            message = f"Risk {score}/100 · {result['risk'].level}"
            if result["alert"]:
                message += "\nAn alert has been created for analyst review."
            QMessageBox.information(self, "Event analyzed", message)
        except Exception as exc:
            session.rollback()
            QMessageBox.critical(self, "Event failed", str(exc))
        finally:
            session.close()

    def import_csv(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Import synthetic behavior CSV", "", "CSV files (*.csv)")
        if not filename:
            return
        self.import_button.setDisabled(True)
        self.import_status.setText("Analyzing imported events in the background…")
        self.import_worker = CSVImportWorker(filename, self.user.id, self)
        self.import_worker.completed.connect(self._import_completed)
        self.import_worker.failed.connect(self._import_failed)
        self.import_worker.start()

    def _import_completed(self, imported: int) -> None:
        self.import_button.setDisabled(False)
        self.import_status.setText(f"Analyzed and stored {imported:,} events.")
        self.refresh()

    def _import_failed(self, error: str) -> None:
        self.import_button.setDisabled(False)
        self.import_status.setText("CSV import failed.")
        QMessageBox.critical(self, "Import failed", f"Could not process this CSV. Check its columns and data types.\n\n{error}")

    def refresh(self) -> None:
        session = SessionLocal()
        try:
            events = list(session.scalars(select(BehaviorEvent).options(joinedload(BehaviorEvent.device), joinedload(BehaviorEvent.risk_score), joinedload(BehaviorEvent.anomaly)).order_by(desc(BehaviorEvent.timestamp)).limit(300)))
            self.table.setRowCount(len(events))
            for row, event in enumerate(events):
                set_cell(self.table, row, 0, event.timestamp.strftime("%Y-%m-%d %H:%M"))
                set_cell(self.table, row, 1, event.device.device_id)
                set_cell(self.table, row, 2, f"{event.login_hour:04.1f}")
                set_cell(self.table, row, 3, event.files_accessed)
                set_cell(self.table, row, 4, event.action_count)
                set_cell(self.table, row, 5, event.failed_login_attempts)
                score = event.risk_score.score if event.risk_score else 0
                level = event.risk_score.level if event.risk_score else "LOW"
                set_cell(self.table, row, 6, f"{score} · {level}", {"CRITICAL": "#b8494c", "HIGH": "#cb8c32"}.get(level))
                set_cell(self.table, row, 7, "ANOMALOUS" if event.anomaly and event.anomaly.detected else "NORMAL")
        finally:
            session.close()