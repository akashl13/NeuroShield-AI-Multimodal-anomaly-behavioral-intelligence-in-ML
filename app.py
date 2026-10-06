from __future__ import annotations

import argparse
from getpass import getpass


def main() -> int:
    parser = argparse.ArgumentParser(description="NEUROSHIELD AI behavioral risk intelligence")
    parser.add_argument("--init-db", action="store_true", help="Create application tables and exit.")
    parser.add_argument("--create-user", metavar="USERNAME", help="Create the initial administrator or an analyst account.")
    args = parser.parse_args()

    from database.connection import SessionLocal
    from database.init_db import initialize_database

    initialize_database()
    if args.init_db:
        print("Database initialized.")
        return 0
    if args.create_user:
        from services.auth_service import register_user

        password = getpass("New password (10+ characters): ")
        confirmation = getpass("Confirm password: ")
        if password != confirmation:
            print("Passwords do not match.")
            return 2
        session = SessionLocal()
        try:
            user = register_user(session, args.create_user, password)
            print(f"Created {user.role} account '{user.username}'.")
            return 0
        except ValueError as exc:
            print(f"Could not create account: {exc}")
            return 2
        finally:
            session.close()

    from PySide6.QtWidgets import QApplication, QDialog

    from gui.login import LoginDialog
    from gui.main_window import MainWindow
    from services.auth_service import revoke_session

    app = QApplication.instance() or QApplication([])
    app.setApplicationName("NEUROSHIELD AI")
    while True:
        login = LoginDialog()
        if login.exec() != QDialog.DialogCode.Accepted:
            break
        window = MainWindow(login.user, login.token)
        window.logout_requested.connect(app.quit)
        window.show()
        app.exec()
        if not window.logged_out:
            break
        session = SessionLocal()
        try:
            revoke_session(session, login.token)
        finally:
            session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())