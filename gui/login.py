from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget
from sqlalchemy import select

from database.connection import SessionLocal
from database.models import User
from gui.theme import APP_STYLE
from services.auth_service import create_session, register_user


class LoginDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("NEUROSHIELD AI | Secure access")
        self.setMinimumWidth(400)
        self.setStyleSheet(APP_STYLE)
        self.user = None
        self.token = ""
        root = QVBoxLayout(self)
        brand = QLabel("NEUROSHIELD <span style='color:#087f8c'>AI</span>")
        brand.setTextFormat(Qt.TextFormat.RichText)
        brand.setStyleSheet("font-size:24px;font-weight:800;color:#15252f;padding:8px 0")
        subtitle = QLabel("BEHAVIORAL RISK INTELLIGENCE")
        subtitle.setObjectName("eyebrow")
        root.addWidget(brand)
        root.addWidget(subtitle)
        self.stack = QStackedWidget()
        self.login_page = self._build_login()
        self.register_page = self._build_register()
        self.stack.addWidget(self.login_page)
        self.stack.addWidget(self.register_page)
        root.addWidget(self.stack)

    def _build_login(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.username = QLineEdit()
        self.username.setPlaceholderText("Your analyst username")
        self.password = QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Username", self.username)
        form.addRow("Password", self.password)
        layout.addLayout(form)
        submit = QPushButton("Sign in")
        submit.clicked.connect(self._login)
        layout.addWidget(submit)
        register = QPushButton("Create an analyst account")
        register.setObjectName("secondary")
        register.clicked.connect(lambda: self.stack.setCurrentWidget(self.register_page))
        layout.addWidget(register)
        return page

    def _build_register(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.new_username = QLineEdit()
        self.new_username.setPlaceholderText("3 to 80 characters")
        self.new_password = QLineEdit()
        self.new_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password = QLineEdit()
        self.confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Username", self.new_username)
        form.addRow("Password", self.new_password)
        form.addRow("Confirm", self.confirm_password)
        layout.addLayout(form)
        create = QPushButton("Register")
        create.clicked.connect(self._register)
        layout.addWidget(create)
        back = QPushButton("Back to sign in")
        back.setObjectName("secondary")
        back.clicked.connect(lambda: self.stack.setCurrentWidget(self.login_page))
        layout.addWidget(back)
        note = QLabel("The first account is provisioned as administrator. New registrations are analysts.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        return page

    def _login(self) -> None:
        session = SessionLocal()
        try:
            self.user, self.token = create_session(session, self.username.text(), self.password.text())
            self.accept()
        except ValueError as exc:
            QMessageBox.warning(self, "Sign-in failed", str(exc))
        finally:
            session.close()

    def _register(self) -> None:
        if self.new_password.text() != self.confirm_password.text():
            QMessageBox.warning(self, "Registration failed", "The passwords do not match.")
            return
        session = SessionLocal()
        try:
            user_count = session.scalar(select(User.id).limit(1))
            register_user(session, self.new_username.text(), self.new_password.text(), "analyst" if user_count else "admin")
            self.username.setText(self.new_username.text())
            self.password.setText(self.new_password.text())
            self.stack.setCurrentWidget(self.login_page)
            QMessageBox.information(self, "Account created", "Your account is ready. Sign in to continue.")
        except ValueError as exc:
            QMessageBox.warning(self, "Registration failed", str(exc))
        finally:
            session.close()