from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QWidget
from sqlalchemy import desc, or_, select
from sqlalchemy.orm import joinedload

from database.connection import SessionLocal
from database.models import Alert, BehaviorEvent, Device, User
from gui.investigation import InvestigationDialog
from gui.widgets import make_table, page_header, set_cell, vertical
from services.alert_service import mark_reviewed, update_alert_triage


class AlertsPage(QWidget):
    def __init__(self, analyst):
        super().__init__()
        self.analyst = analyst
        self.layout = vertical(self)
        self.layout.addLayout(page_header("Alert queue", "Prioritize elevated behavioral risk and record investigation outcomes."))
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search alert, user, or device")
        self.search.returnPressed.connect(self.refresh)
        self.status_filter = QComboBox()
        self.status_filter.addItem("All statuses", "")
        for status in ("open", "acknowledged", "investigating", "resolved", "false_positive"):
            self.status_filter.addItem(status.replace("_", " ").title(), status)
        self.status_filter.currentIndexChanged.connect(self.refresh)
        filters.addWidget(self.search, 1)
        filters.addWidget(self.status_filter)
        self.layout.addLayout(filters)

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

        triage = QHBoxLayout()
        self.status_action = QComboBox()
        for status in ("open", "acknowledged", "investigating", "resolved", "false_positive"):
            self.status_action.addItem(status.replace("_", " ").title(), status)
        self.assignee_action = QComboBox()
        apply_button = QPushButton("Apply triage")
        apply_button.clicked.connect(self.apply_triage)
        triage.addWidget(QLabel("Set status"))
        triage.addWidget(self.status_action)
        triage.addWidget(QLabel("Assign to"))
        triage.addWidget(self.assignee_action, 1)
        triage.addWidget(apply_button)
        self.layout.addLayout(triage)

        self.table = make_table(["Created", "Severity", "Alert", "User", "Device", "Risk", "Status", "Assigned analyst"])
        self.table.doubleClicked.connect(self.open_investigation)
        self.layout.addWidget(self.table, 1)
        self.empty_label = QLabel("No alerts match the current filters.")
        self.empty_label.setObjectName("muted")
        self.layout.addWidget(self.empty_label)
        self.refresh()

    def selected_alert_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0 or self.table.item(row, 0) is None:
            return None
        return int(self.table.item(row, 0).data(256))

    def refresh(self, *_args) -> None:
        session = SessionLocal()
        try:
            users = list(session.scalars(select(User).where(User.is_active.is_(True), User.role.in_(("admin", "analyst"))).order_by(User.username)))
            current_assignee = self.assignee_action.currentData() or self.analyst.id
            self.assignee_action.clear()
            for user in users:
                self.assignee_action.addItem(user.username, user.id)
            selected_index = self.assignee_action.findData(current_assignee)
            self.assignee_action.setCurrentIndex(max(0, selected_index))

            statement = select(Alert).options(
                joinedload(Alert.event).joinedload(BehaviorEvent.user),
                joinedload(Alert.event).joinedload(BehaviorEvent.device),
                joinedload(Alert.event).joinedload(BehaviorEvent.risk_score),
            )
            status = self.status_filter.currentData()
            if status:
                statement = statement.where(Alert.status == status)
            search = self.search.text().strip()
            if search:
                pattern = f"%{search}%"
                statement = statement.join(Alert.event).join(BehaviorEvent.user).join(BehaviorEvent.device).where(or_(
                    Alert.title.ilike(pattern), Alert.message.ilike(pattern),
                    User.username.ilike(pattern), Device.device_id.ilike(pattern),
                ))
            alerts = list(session.scalars(statement.order_by(desc(Alert.created_at)).limit(500)).unique())
            user_names = {user.id: user.username for user in users}
            self.table.setRowCount(len(alerts))
            for row, alert in enumerate(alerts):
                set_cell(self.table, row, 0, alert.created_at.strftime("%Y-%m-%d %H:%M"))
                self.table.item(row, 0).setData(256, alert.id)
                set_cell(self.table, row, 1, alert.severity, {"CRITICAL": "#b8494c", "HIGH": "#cb8c32", "MEDIUM": "#3976a8"}.get(alert.severity))
                set_cell(self.table, row, 2, alert.title)
                set_cell(self.table, row, 3, alert.event.user.username)
                set_cell(self.table, row, 4, alert.event.device.device_id)
                risk = alert.event.risk_score
                set_cell(self.table, row, 5, f"{risk.score} · {risk.level}" if risk else "—")
                set_cell(self.table, row, 6, alert.status.replace("_", " ").title())
                set_cell(self.table, row, 7, user_names.get(alert.reviewed_by, "Unassigned"))
            self.empty_label.setVisible(not alerts)
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

    def apply_triage(self) -> None:
        alert_id = self.selected_alert_id()
        if alert_id is None:
            QMessageBox.information(self, "Select an alert", "Choose an alert row to update.")
            return
        session = SessionLocal()
        try:
            alert = session.get(Alert, alert_id)
            if alert is None:
                raise ValueError("This alert no longer exists.")
            update_alert_triage(session, alert, self.status_action.currentData(), self.assignee_action.currentData())
            self.refresh()
        except Exception as exc:
            session.rollback()
            QMessageBox.critical(self, "Triage update failed", str(exc))
        finally:
            session.close()