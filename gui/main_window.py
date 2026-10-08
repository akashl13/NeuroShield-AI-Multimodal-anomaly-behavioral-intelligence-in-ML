from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from config.settings import DATABASE_URL
from database.connection import SessionLocal
from gui.alerts import AlertsPage
from gui.analytics import AnalyticsPage
from gui.dashboard import DashboardPage
from gui.events import EventsPage
from gui.intelligence import UserDevicePage
from gui.investigations import InvestigationsPage
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
        self.setMinimumSize(980, 640)
        self.setStyleSheet(APP_STYLE)
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(224)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(14, 22, 14, 16)
        sidebar_layout.setSpacing(7)
        brand = QLabel("NEUROSHIELD <span style='color:#63d0bd'>AI</span>")
        brand.setTextFormat(Qt.TextFormat.RichText)
        brand.setStyleSheet("font-size:18px;font-weight:800;padding:0 8px 4px")
        sidebar_layout.addWidget(brand)
        brand_detail = QLabel("BEHAVIORAL RISK INTELLIGENCE")
        brand_detail.setStyleSheet("color:#87a2b1;font-size:9px;letter-spacing:1px;padding:0 8px 20px")
        sidebar_layout.addWidget(brand_detail)
        section_label = QLabel("WORKSPACE")
        section_label.setStyleSheet("color:#718c9d;font-size:9px;font-weight:700;letter-spacing:1px;padding:8px")
        sidebar_layout.addWidget(section_label)
        nav_items = [("Overview", "◈"), ("Events", "▤"), ("Alerts", "!"), ("Investigations", "⌕"), ("Analytics", "⌁"), ("Users & devices", "▦"), ("Settings", "⚙")]
        self.stack = QStackedWidget()
        self.dashboard_page = DashboardPage(user)
        self.events_page = EventsPage(user)
        self.alerts_page = AlertsPage(user)
        self.investigations_page = InvestigationsPage(user)
        self.analytics_page = AnalyticsPage()
        self.intelligence_page = UserDevicePage()
        self.settings_page = SettingsPage(self.analytics_page)
        self.pages = [self.dashboard_page, self.events_page, self.alerts_page, self.investigations_page, self.analytics_page, self.intelligence_page, self.settings_page]
        self.dashboard_page.load_demo_requested.connect(self.events_page.load_demo_data)
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
        privacy = QLabel("DEMO-SAFE WORKSPACE\nSynthetic telemetry only")
        privacy.setStyleSheet("color:#87a2b1;font-size:9px;line-height:1.5;padding:8px")
        sidebar_layout.addWidget(privacy)
        root_layout.addWidget(sidebar)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        header = QFrame()
        header.setObjectName("topbar")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 11, 24, 11)
        workspace_label = QLabel("Security operations")
        workspace_label.setStyleSheet("font-size:13px;font-weight:600;color:#536a7a")
        header_layout.addWidget(workspace_label)
        header_layout.addStretch(1)
        environment_label = QLabel("LOCAL · DEMO" if not DATABASE_URL.startswith(("postgresql", "postgres")) else "NEON")
        environment_label.setStyleSheet("font-size:10px;font-weight:700;color:#52736d;background:#eaf3ef;border-radius:4px;padding:6px 8px")
        header_layout.addWidget(environment_label)
        user_label = QLabel(f"{user.username}  ·  {user.role.title()}")
        user_label.setStyleSheet("font-weight:600;color:#294356;background:#f1f6f8;border-radius:14px;padding:7px 12px")
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