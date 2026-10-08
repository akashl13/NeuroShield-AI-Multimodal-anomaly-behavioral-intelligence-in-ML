from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QWidget
from sqlalchemy import desc, or_, select

from database.connection import SessionLocal
from database.models import Alert, BehaviorEvent, Device, Investigation, User
from gui.investigation import InvestigationDialog
from gui.widgets import make_table, page_header, set_cell, vertical


class InvestigationsPage(QWidget):
    def __init__(self, analyst):
        super().__init__()
        self.analyst = analyst
        self.layout = vertical(self)
        self.layout.addLayout(page_header("Investigation workspace", "Review analyst-owned notes and the alert context behind each case."))
        controls = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search alert, user, or device")
        self.search.returnPressed.connect(self.refresh)
        self.status = QComboBox()
        self.status.addItem("All investigations", "")
        self.status.addItem("In review", "in_review")
        self.status.addItem("Resolved", "resolved")
        self.status.currentIndexChanged.connect(self.refresh)
        refresh_button = QPushButton("Refresh")
        refresh_button.setObjectName("secondary")
        refresh_button.clicked.connect(self.refresh)
        controls.addWidget(self.search, 1)
        controls.addWidget(self.status)
        controls.addWidget(refresh_button)
        self.layout.addLayout(controls)
        self.table = make_table(["Updated", "Alert", "Severity", "User", "Device", "Analyst", "Status", "Notes"])
        self.table.doubleClicked.connect(self.open_selected)
        self.layout.addWidget(self.table, 1)
        self.empty_label = QLabel("No investigations available. Start a review from an alert.")
        self.empty_label.setObjectName("muted")
        self.layout.addWidget(self.empty_label)
        open_button = QPushButton("Open investigation")
        open_button.clicked.connect(self.open_selected)
        self.layout.addWidget(open_button, 0, Qt.AlignmentFlag.AlignRight)
        self.refresh()

    def refresh(self, *_args) -> None:
        session = SessionLocal()
        try:
            statement = (
                select(Investigation, Alert, BehaviorEvent, User, Device)
                .join(Alert, Investigation.alert_id == Alert.id)
                .join(BehaviorEvent, Alert.event_id == BehaviorEvent.id)
                .join(User, BehaviorEvent.user_id == User.id)
                .join(Device, BehaviorEvent.device_id == Device.id)
            )
            status = self.status.currentData()
            if status:
                statement = statement.where(Investigation.outcome == status)
            search = self.search.text().strip()
            if search:
                pattern = f"%{search}%"
                statement = statement.where(or_(
                    Alert.title.ilike(pattern), Alert.message.ilike(pattern),
                    User.username.ilike(pattern), Device.device_id.ilike(pattern),
                ))
            rows = session.execute(statement.order_by(desc(Investigation.updated_at)).limit(500)).all()
            self.table.setRowCount(len(rows))
            for row, (investigation, alert, event, user, device) in enumerate(rows):
                set_cell(self.table, row, 0, investigation.updated_at.strftime("%Y-%m-%d %H:%M"))
                self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, alert.id)
                set_cell(self.table, row, 1, alert.title)
                set_cell(self.table, row, 2, alert.severity, {"CRITICAL": "#b8494c", "HIGH": "#cb8c32"}.get(alert.severity))
                set_cell(self.table, row, 3, user.username)
                set_cell(self.table, row, 4, device.device_id)
                set_cell(self.table, row, 5, self.analyst.username if investigation.analyst_id == self.analyst.id else "Other analyst")
                set_cell(self.table, row, 6, investigation.outcome.replace("_", " ").title())
                set_cell(self.table, row, 7, investigation.notes or "—")
            self.empty_label.setVisible(not rows)
        except Exception:
            QMessageBox.critical(self, "Investigations unavailable", "Could not load investigation records. Check the database connection and try again.")
        finally:
            session.close()

    def open_selected(self, *_args) -> None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        alert_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        if alert_id is None:
            QMessageBox.information(self, "Select an investigation", "Choose an investigation row to open.")
            return
        InvestigationDialog(alert_id, self.analyst, self).exec()
        self.refresh()