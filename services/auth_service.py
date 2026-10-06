from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import Session

from config.settings import SESSION_TTL_MINUTES
from database.models import AuthSession, User


def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 UTF-8 bytes.")
    if len(password) < 10:
        raise ValueError("Password must contain at least 10 characters.")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def register_user(session: Session, username: str, password: str, role: str = "analyst") -> User:
    username = username.strip()
    if not 3 <= len(username) <= 80:
        raise ValueError("Username must be between 3 and 80 characters.")
    if session.scalar(select(User.id).where(User.username == username)):
        raise ValueError("That username is already registered.")
    user_count = session.scalar(select(User.id).limit(1))
    if role == "admin" and user_count is not None:
        raise ValueError("Admin access can only be assigned to the first registered account.")
    if user_count is None:
        role = "admin"
    if role not in {"admin", "analyst"}:
        role = "analyst"
    user = User(username=username, password_hash=hash_password(password), role=role)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def create_session(session: Session, username: str, password: str) -> tuple[User, str]:
    user = session.scalar(select(User).where(User.username == username.strip(), User.is_active.is_(True)))
    if user is None or not bcrypt.checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8")):
        raise ValueError("Invalid username or password.")
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    session.add(AuthSession(user_id=user.id, token_hash=token_hash, expires_at=datetime.now(timezone.utc) + timedelta(minutes=SESSION_TTL_MINUTES)))
    session.commit()
    return user, raw_token


def validate_session(session: Session, raw_token: str) -> User | None:
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    auth_session = session.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash))
    if auth_session is None:
        return None
    expires_at = auth_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc) or not auth_session.user.is_active:
        session.delete(auth_session)
        session.commit()
        return None
    return auth_session.user


def revoke_session(session: Session, raw_token: str) -> None:
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    auth_session = session.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash))
    if auth_session is not None:
        session.delete(auth_session)
        session.commit()