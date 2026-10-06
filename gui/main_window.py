from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from database.connection import SessionLocal
from gui.alerts import AlertsPage
from gui.analytics import AnalyticsPage
from gui.dashboard import DashboardPage
from gui.events import EventsPage
from gui.settings import SettingsPage
from gui.theme import APP_STYLE
from services.auth_service import validate_session


class MainWindow(QMainWindow):
    logout_requested = Signal(str)

    def __init__(self, user, token: str):
        super().__init__()
        self.user = user
        self.token = token
        self.logged_out = False
        self.setWindowTitle("NEUROSHIELD AI | Behavioral Risk Intelligence")
        self.resize(1440, 900)
        self.setMinimumSize(1080, 680)
        self.setStyleSheet(APP_STYLE)
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(210)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 22, 12, 16)
        brand = QLabel("NEUROSHIELD\n<span style='color:#50c0bc'>AI</span>")
        brand.setTextFormat(Qt.TextFormat.RichText)
        brand.setStyleSheet("font-size:19px;font-weight:800;padding:0 8px 14px")
        sidebar_layout.addWidget(brand)
        nav_items = [("Overview", "◈"), ("Events", "▤"), ("Alerts", "!"), ("Analytics", "⌁"), ("Settings", "⚙")]
        self.stack = QStackedWidget()
        self.dashboard_page = DashboardPage()
        self.events_page = EventsPage(user)
        self.alerts_page = AlertsPage(user)
        self.analytics_page = AnalyticsPage()
        self.settings_page = SettingsPage(self.analytics_page)
        self.pages = [self.dashboard_page, self.events_page, self.alerts_page, self.analytics_page, self.settings_page]
        self.nav_buttons: list[QPushButton] = []
        for index, (label, icon) in enumerate(nav_items):
            button = QPushButton(f"{icon}    {label}")
            button.setObjectName("nav")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, target=index: self.show_page(target))
            if label == "Settings" and user.role != "admin":
                button.hide()
            self.nav_buttons.append(button)
            sidebar_layout.addWidget(button)
            self.stack.addWidget(self.pages[index])
        sidebar_layout.addStretch(1)
        privacy = QLabel("SYNTHETIC TELEMETRY\nNo real user data")
        privacy.setStyleSheet("color:#85a0a7;font-size:10px;padding:8px")
        sidebar_layout.addWidget(privacy)
        root_layout.addWidget(sidebar)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        header = QFrame()
        header.setStyleSheet("background:white;border-bottom:1px solid #e1e7e9")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(22, 9, 22, 9)
        header_layout.addWidget(QLabel("BEHAVIORAL RISK INTELLIGENCE"))
        header_layout.addStretch(1)
        user_label = QLabel(f"{user.username}  ·  {user.role.title()}")
        user_label.setStyleSheet("font-weight:600;color:#3e535d")
        header_layout.addWidget(user_label)
        logout = QPushButton("Log out")
        logout.setObjectName("secondary")
        logout.clicked.connect(self.logout)
        header_layout.addWidget(logout)
        content_layout.addWidget(header)
        content_layout.addWidget(self.stack, 1)
        root_layout.addWidget(content, 1)
        self.setCentralWidget(root)
        self.show_page(0)
        self.session_timer = QTimer(self)
        self.session_timer.setInterval(60_000)
        self.session_timer.timeout.connect(self._check_session)
        self.session_timer.start()

    def show_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for position, button in enumerate(self.nav_buttons):
            button.setChecked(position == index)
        refresh = getattr(self.pages[index], "refresh", None)
        if refresh:
            refresh()

    def _check_session(self) -> None:
        session = SessionLocal()
        try:
            if validate_session(session, self.token) is None:
                QMessageBox.information(self, "Session expired", "Please sign in again to continue.")
                self.logout()
        finally:
            session.close()

    def logout(self) -> None:
        if not self.logged_out:
            self.logged_out = True
            self.session_timer.stop()
            self.logout_requested.emit(self.token)
            self.close()

    def closeEvent(self, event) -> None:
        for page in self.pages:
            for worker_name in ("worker", "import_worker"):
                worker = getattr(page, worker_name, None)
                if worker is not None and worker.isRunning():
                    worker.wait()
        super().closeEvent(event)