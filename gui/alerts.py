from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QMessageBox, QPushButton, QWidget
from sqlalchemy import desc, select

from database.connection import SessionLocal
from database.models import Alert
from gui.investigation import InvestigationDialog
from gui.widgets import make_table, page_header, set_cell, vertical
from services.alert_service import mark_reviewed


class AlertsPage(QWidget):
    def __init__(self, analyst):
        super().__init__()
        self.analyst = analyst
        self.layout = vertical(self)
        self.layout.addLayout(page_header("Alert queue", "Prioritize elevated behavioral risk and record investigation outcomes."))
        actions = QHBoxLayout()
        investigate = QPushButton("Open investigation")
        investigate.clicked.connect(self.open_investigation)
        review = QPushButton("Mark reviewed")
        review.setObjectName("secondary")
        review.clicked.connect(self.mark_reviewed)
        actions.addWidget(investigate)
        actions.addWidget(review)
        actions.addStretch(1)
        self.layout.addLayout(actions)
        self.table = make_table(["Created", "Severity", "Title", "Status", "Analyst message"])
        self.table.doubleClicked.connect(self.open_investigation)
        self.layout.addWidget(self.table, 1)
        self.refresh()

    def selected_alert_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0 or self.table.item(row, 0) is None:
            return None
        return int(self.table.item(row, 0).data(256))

    def refresh(self) -> None:
        session = SessionLocal()
        try:
            alerts = list(session.scalars(select(Alert).order_by(desc(Alert.created_at)).limit(500)))
            self.table.setRowCount(len(alerts))
            for row, alert in enumerate(alerts):
                set_cell(self.table, row, 0, alert.created_at.strftime("%Y-%m-%d %H:%M"))
                self.table.item(row, 0).setData(256, alert.id)
                set_cell(self.table, row, 1, alert.severity, {"CRITICAL": "#b8494c", "HIGH": "#cb8c32", "MEDIUM": "#3976a8"}.get(alert.severity))
                set_cell(self.table, row, 2, alert.title)
                set_cell(self.table, row, 3, alert.status.title())
                set_cell(self.table, row, 4, alert.message)
        finally:
            session.close()

    def open_investigation(self, *_args) -> None:
        alert_id = self.selected_alert_id()
        if alert_id is None:
            QMessageBox.information(self, "Select an alert", "Choose an alert row to investigate.")
            return
        dialog = InvestigationDialog(alert_id, self.analyst, self)
        dialog.exec()
        self.refresh()

    def mark_reviewed(self) -> None:
        alert_id = self.selected_alert_id()
        if alert_id is None:
            QMessageBox.information(self, "Select an alert", "Choose an alert row to mark reviewed.")
            return
        session = SessionLocal()
        try:
            alert = session.get(Alert, alert_id)
            if alert:
                mark_reviewed(session, alert, self.analyst.id)
            self.refresh()
        except Exception as exc:
            session.rollback()
            QMessageBox.critical(self, "Review failed", str(exc))
        finally:
            session.close()