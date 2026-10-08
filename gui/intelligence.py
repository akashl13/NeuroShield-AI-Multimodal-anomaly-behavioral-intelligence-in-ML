from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QTabWidget, QWidget
from sqlalchemy import case, desc, func, or_, select

from database.connection import SessionLocal
from database.models import Alert, Anomaly, BehaviorEvent, Device, RiskScore, User
from gui.widgets import make_table, page_header, set_cell, vertical


class UserDevicePage(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = vertical(self)
        self.layout.addLayout(page_header("Users & devices", "Compare observed activity, risk, and alert volume from stored events."))
        controls = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter users or device identifiers")
        self.search.returnPressed.connect(self.refresh)
        refresh_button = QPushButton("Refresh")
        refresh_button.setObjectName("secondary")
        refresh_button.clicked.connect(self.refresh)
        controls.addWidget(self.search, 1)
        controls.addWidget(refresh_button)
        self.layout.addLayout(controls)
        self.tabs = QTabWidget()
        self.user_table = make_table(["User", "Role", "Events", "Average risk", "Anomalies", "Open alerts", "Last activity", "Risk band"])
        self.device_table = make_table(["Device", "User", "Events", "Average risk", "Anomalies", "Last activity", "Risk band"])
        self.tabs.addTab(self.user_table, "Users")
        self.tabs.addTab(self.device_table, "Devices")
        self.layout.addWidget(self.tabs, 1)
        self.empty_label = QLabel("No users or devices available yet.")
        self.empty_label.setObjectName("muted")
        self.layout.addWidget(self.empty_label)
        self.refresh()

    @staticmethod
    def _risk_band(score: float) -> str:
        if score >= 76:
            return "CRITICAL"
        if score >= 51:
            return "HIGH"
        if score >= 26:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _time_label(timestamp: datetime | None) -> str:
        return timestamp.strftime("%Y-%m-%d %H:%M") if timestamp else "—"

    def refresh(self, *_args) -> None:
        session = SessionLocal()
        try:
            pattern = f"%{self.search.text().strip()}%"
            user_query = select(User).order_by(User.username).limit(500)
            if self.search.text().strip():
                user_query = user_query.where(or_(User.username.ilike(pattern), User.role.ilike(pattern)))
            users = list(session.scalars(user_query))
            event_stats = session.execute(
                select(
                    BehaviorEvent.user_id,
                    func.count(BehaviorEvent.id),
                    func.coalesce(func.avg(RiskScore.score), 0),
                    func.coalesce(func.sum(case((Anomaly.detected.is_(True), 1), else_=0)), 0),
                    func.max(BehaviorEvent.timestamp),
                )
                .outerjoin(RiskScore, RiskScore.event_id == BehaviorEvent.id)
                .outerjoin(Anomaly, Anomaly.event_id == BehaviorEvent.id)
                .group_by(BehaviorEvent.user_id)
            ).all()
            stats_by_user = {user_id: (int(count), float(avg), int(anomalies), last_seen) for user_id, count, avg, anomalies, last_seen in event_stats}
            alert_stats = dict(session.execute(
                select(BehaviorEvent.user_id, func.count(Alert.id))
                .join(Alert, Alert.event_id == BehaviorEvent.id)
                .where(Alert.status.in_(("open", "acknowledged", "investigating")))
                .group_by(BehaviorEvent.user_id)
            ).all())
            self.user_table.setRowCount(len(users))
            for row, user in enumerate(users):
                count, average, anomalies, last_seen = stats_by_user.get(user.id, (0, 0.0, 0, None))
                set_cell(self.user_table, row, 0, user.username)
                set_cell(self.user_table, row, 1, user.role.title())
                set_cell(self.user_table, row, 2, count)
                set_cell(self.user_table, row, 3, f"{average:.1f}" if count else "—")
                set_cell(self.user_table, row, 4, anomalies)
                set_cell(self.user_table, row, 5, int(alert_stats.get(user.id, 0)))
                set_cell(self.user_table, row, 6, self._time_label(last_seen))
                set_cell(self.user_table, row, 7, self._risk_band(average) if count else "—")

            device_query = (
                select(
                    Device.device_id, User.username,
                    func.count(BehaviorEvent.id),
                    func.coalesce(func.avg(RiskScore.score), 0),
                    func.coalesce(func.sum(case((Anomaly.detected.is_(True), 1), else_=0)), 0),
                    func.max(BehaviorEvent.timestamp),
                )
                .join(User, User.id == Device.user_id)
                .outerjoin(BehaviorEvent, BehaviorEvent.device_id == Device.id)
                .outerjoin(RiskScore, RiskScore.event_id == BehaviorEvent.id)
                .outerjoin(Anomaly, Anomaly.event_id == BehaviorEvent.id)
                .group_by(Device.id, Device.device_id, User.username)
                .order_by(desc(func.count(BehaviorEvent.id)), Device.device_id)
                .limit(500)
            )
            if self.search.text().strip():
                device_query = device_query.where(or_(Device.device_id.ilike(pattern), User.username.ilike(pattern)))
            devices = session.execute(device_query).all()
            self.device_table.setRowCount(len(devices))
            for row, (device_id, username, count, average, anomalies, last_seen) in enumerate(devices):
                average = float(average)
                set_cell(self.device_table, row, 0, device_id)
                set_cell(self.device_table, row, 1, username)
                set_cell(self.device_table, row, 2, count)
                set_cell(self.device_table, row, 3, f"{average:.1f}" if count else "—")
                set_cell(self.device_table, row, 4, int(anomalies))
                set_cell(self.device_table, row, 5, self._time_label(last_seen))
                set_cell(self.device_table, row, 6, self._risk_band(average) if count else "—")
            self.empty_label.setVisible(not users and not devices)
        finally:
            session.close()