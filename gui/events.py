from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget
from sqlalchemy import desc, select
from sqlalchemy.orm import joinedload

from database.connection import SessionLocal
from database.crud import list_event_page
from database.models import Alert, BehaviorEvent, User
from gui.widgets import make_table, page_header, set_cell, vertical
from ml.explainability import explain_event
from services.event_service import baseline_for_user, import_csv_events, record_event
from services.simulation_service import generate_behavior_event, generate_demo_events


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


class EventDetailsDialog(QDialog):
    def __init__(self, event_id: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Behavior event details")
        self.setMinimumSize(620, 560)
        layout = QVBoxLayout(self)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        layout.addWidget(self.details, 1)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)

        session = SessionLocal()
        try:
            event = session.scalar(select(BehaviorEvent).options(
                joinedload(BehaviorEvent.user),
                joinedload(BehaviorEvent.device),
                joinedload(BehaviorEvent.risk_score),
                joinedload(BehaviorEvent.anomaly),
                joinedload(BehaviorEvent.prediction),
            ).where(BehaviorEvent.id == event_id))
            if event is None:
                self.details.setPlainText("This event is no longer available.")
                return
            alert = session.scalar(select(Alert).where(Alert.event_id == event.id).order_by(desc(Alert.created_at)).limit(1))
            features = {key: getattr(event, key) for key in (
                "login_hour", "session_duration_minutes", "files_accessed", "action_count", "failed_login_attempts",
                "network_bytes_mb", "cpu_percent", "network_zone", "location_category", "application_usage", "device_was_known",
            )}
            baseline = baseline_for_user(session, event.user_id, event.device_id)
            explanation = explain_event(features, event.anomaly.score if event.anomaly else 0, baseline)
            risk_factors = event.risk_score.factors if event.risk_score else {}
            risk_items = "".join(f"<li>{escape(str(label))}: {points}</li>" for label, points in risk_factors.items())
            shap_values = explanation["shap_values"]
            if shap_values:
                shap_items = "".join(
                    f"<li>{escape(label)}: {value:+.4f}</li>"
                    for label, value in sorted(shap_values.items(), key=lambda item: abs(item[1]), reverse=True)[:6]
                )
                explanation_html = f"<h3>SHAP contributors</h3><ul>{shap_items}</ul>"
            else:
                explanation_html = "<p>Explainability unavailable for this prediction.</p>"
            risk = event.risk_score
            prediction = event.prediction
            anomaly = event.anomaly
            self.details.setHtml(f"""
                <h2>Event #{event.id}</h2>
                <p><b>Timestamp:</b> {event.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}<br>
                <b>User:</b> {escape(event.user.username)}<br>
                <b>Device:</b> {escape(event.device.device_id)}<br>
                <b>Network:</b> {escape(event.network_zone)} · {escape(event.location_category)}<br>
                <b>Alert status:</b> {escape(alert.status.title() if alert else 'No alert')}</p>
                <h3>Behavioral features</h3>
                <p>Login {event.login_hour:.1f}:00 · Session {event.session_duration_minutes:.1f} min ·
                Files {event.files_accessed} · Actions {event.action_count} · Failed logins {event.failed_login_attempts}<br>
                Network {event.network_bytes_mb:.1f} MB · CPU {event.cpu_percent:.1f}% ·
                Device {'known' if event.device_was_known else 'new'}</p>
                <h3>Model and risk</h3>
                <p><b>Prediction:</b> {escape(prediction.classification if prediction else 'Unavailable')} ·
                {escape(prediction.model_name if prediction else 'No model recorded')}<br>
                <b>Anomaly:</b> {'Detected' if anomaly and anomaly.detected else 'Not detected' if anomaly else 'Unavailable'} ·
                {anomaly.score if anomaly else 'N/A'}<br>
                <b>Risk:</b> {risk.score if risk else 'N/A'} / 100 · {escape(risk.level if risk else 'Unavailable')}</p>
                <h3>Stored risk factors</h3><ul>{risk_items or '<li>No risk factors recorded.</li>'}</ul>
                {explanation_html}
            """)
        except Exception:
            self.details.setPlainText("Event details could not be loaded. Check the database connection and try again.")
        finally:
            session.close()


class EventsPage(QWidget):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.page = 1
        self.total_events = 0
        self.layout = vertical(self)
        self.layout.addLayout(page_header("Behavior events", "Generate synthetic activity or import an anonymized CSV into the analysis pipeline."))
        controls = QHBoxLayout()
        normal = QPushButton("Generate normal event")
        normal.clicked.connect(lambda: self.generate(False))
        suspicious = QPushButton("Generate suspicious event")
        suspicious.setObjectName("danger")
        suspicious.clicked.connect(lambda: self.generate(True))
        demo = QPushButton("Load 30 demo events")
        demo.setObjectName("secondary")
        demo.clicked.connect(self.load_demo_data)
        self.import_button = QPushButton("Import CSV")
        self.import_button.setObjectName("secondary")
        self.import_button.clicked.connect(self.import_csv)
        controls.addWidget(normal)
        controls.addWidget(suspicious)
        controls.addWidget(demo)
        controls.addStretch(1)
        controls.addWidget(self.import_button)
        self.layout.addLayout(controls)
        self.import_status = QLabel("Demo data is synthetic and additive. CSV imports are anonymized and limited to 10,000 events per file.")
        self.import_status.setObjectName("muted")
        self.layout.addWidget(self.import_status)

        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search user, device, app, or network")
        self.search.returnPressed.connect(self.apply_filters)
        search_button = QPushButton("Search")
        search_button.setObjectName("secondary")
        search_button.clicked.connect(self.apply_filters)
        self.risk_filter = QComboBox()
        self.risk_filter.addItem("All risk levels", "")
        for level in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
            self.risk_filter.addItem(level.title(), level)
        self.anomaly_filter = QComboBox()
        self.anomaly_filter.addItem("All events", "")
        self.anomaly_filter.addItem("Anomalous", "anomalous")
        self.anomaly_filter.addItem("Normal", "normal")
        self.sort_filter = QComboBox()
        self.sort_filter.addItem("Newest first", "newest")
        self.sort_filter.addItem("Highest risk", "highest risk")
        self.sort_filter.addItem("Oldest first", "oldest")
        for control in (self.risk_filter, self.anomaly_filter, self.sort_filter):
            control.currentIndexChanged.connect(self.apply_filters)
        filters.addWidget(self.search, 1)
        filters.addWidget(search_button)
        filters.addWidget(self.risk_filter)
        filters.addWidget(self.anomaly_filter)
        filters.addWidget(self.sort_filter)
        self.layout.addLayout(filters)

        self.table = make_table(["Timestamp", "User", "Device", "Event type", "Source", "Risk", "Level", "Anomaly", "Model", "Status"])
        self.table.doubleClicked.connect(self.open_selected_event)
        self.layout.addWidget(self.table, 1)
        self.empty_label = QLabel("No matching events. Generate synthetic activity to begin analysis.")
        self.empty_label.setObjectName("muted")
        self.layout.addWidget(self.empty_label)
        paging = QHBoxLayout()
        self.page_label = QLabel()
        self.page_label.setObjectName("muted")
        previous = QPushButton("Previous")
        previous.setObjectName("secondary")
        previous.clicked.connect(self.previous_page)
        self.next_button = QPushButton("Next")
        self.next_button.setObjectName("secondary")
        self.next_button.clicked.connect(self.next_page)
        details_button = QPushButton("Event details")
        details_button.clicked.connect(self.open_selected_event)
        paging.addWidget(self.page_label, 1)
        paging.addWidget(previous)
        paging.addWidget(self.next_button)
        paging.addWidget(details_button)
        self.previous_button = previous
        self.layout.addLayout(paging)
        self.refresh()

    def apply_filters(self, *_args) -> None:
        self.page = 1
        self.refresh()

    def previous_page(self) -> None:
        if self.page > 1:
            self.page -= 1
            self.refresh()

    def next_page(self) -> None:
        if self.page * 50 < self.total_events:
            self.page += 1
            self.refresh()

    def selected_event_id(self) -> int | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def open_selected_event(self, *_args) -> None:
        event_id = self.selected_event_id()
        if event_id is None:
            QMessageBox.information(self, "Select an event", "Choose an event row to inspect.")
            return
        EventDetailsDialog(event_id, self).exec()

    def generate(self, suspicious: bool) -> None:
        session = SessionLocal()
        try:
            result = record_event(session, self.user, generate_behavior_event(self.user.username, suspicious))
            score = result["risk"].score
            self.page = 1
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

    def load_demo_data(self) -> None:
        choice = QMessageBox.question(
            self,
            "Load synthetic demo data",
            "Add 30 synthetic events across the last 14 days for this account? "
            "This creates normal activity and suspicious examples with alerts; existing records are not changed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        session = SessionLocal()
        try:
            count = generate_demo_events(session, self.user)
            self.import_status.setText(f"Added {count} synthetic events for {self.user.username}. Existing records were kept.")
            self.page = 1
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Demo data failed", str(exc))
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
        self.page = 1
        self.refresh()

    def _import_failed(self, error: str) -> None:
        self.import_button.setDisabled(False)
        self.import_status.setText("CSV import failed.")
        QMessageBox.critical(self, "Import failed", f"Could not process this CSV. Check its columns and data types.\n\n{error}")

    def refresh(self) -> None:
        session = SessionLocal()
        try:
            events, self.total_events = list_event_page(
                session,
                page=self.page,
                page_size=50,
                search=self.search.text(),
                risk_level=self.risk_filter.currentData(),
                anomaly_status=self.anomaly_filter.currentData(),
                sort_by=self.sort_filter.currentData(),
            )
            alert_rows = session.scalars(select(Alert).where(Alert.event_id.in_([event.id for event in events])).order_by(desc(Alert.created_at))) if events else []
            statuses = {}
            for alert in alert_rows:
                statuses.setdefault(alert.event_id, alert.status.title())
            self.table.setRowCount(len(events))
            for row, event in enumerate(events):
                set_cell(self.table, row, 0, event.timestamp.strftime("%Y-%m-%d %H:%M"))
                self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, event.id)
                set_cell(self.table, row, 1, event.user.username)
                set_cell(self.table, row, 2, event.device.device_id)
                set_cell(self.table, row, 3, "Synthetic anomaly" if event.is_synthetic_anomaly else "Behavior event")
                set_cell(self.table, row, 4, event.network_zone)
                score = event.risk_score.score if event.risk_score else "—"
                level = event.risk_score.level if event.risk_score else "—"
                set_cell(self.table, row, 5, score)
                set_cell(self.table, row, 6, level, {"CRITICAL": "#b8494c", "HIGH": "#cb8c32", "MEDIUM": "#3976a8"}.get(level))
                set_cell(self.table, row, 7, "ANOMALOUS" if event.anomaly and event.anomaly.detected else "NORMAL")
                set_cell(self.table, row, 8, event.prediction.model_name if event.prediction else "Unavailable")
                set_cell(self.table, row, 9, statuses.get(event.id, "No alert"))
            self.empty_label.setVisible(not events)
            last_page = max(1, (self.total_events + 49) // 50)
            self.page_label.setText(f"Page {self.page} of {last_page} · {self.total_events:,} events")
            self.previous_button.setEnabled(self.page > 1)
            self.next_button.setEnabled(self.page < last_page)
        finally:
            session.close()