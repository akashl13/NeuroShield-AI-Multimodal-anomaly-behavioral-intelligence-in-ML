from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.connection import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="analyst")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    events: Mapped[list[BehaviorEvent]] = relationship(back_populates="user")
    sessions: Mapped[list[AuthSession]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (UniqueConstraint("user_id", "device_id", name="uq_device_user_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(100), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    events: Mapped[list[BehaviorEvent]] = relationship(back_populates="device")


class BehaviorEvent(Base):
    __tablename__ = "behavior_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    login_hour: Mapped[float] = mapped_column(Float)
    ip_address: Mapped[str] = mapped_column(String(64), default="192.0.2.10")
    network_zone: Mapped[str] = mapped_column(String(30), default="office")
    session_duration_minutes: Mapped[float] = mapped_column(Float)
    files_accessed: Mapped[int] = mapped_column(Integer)
    action_count: Mapped[int] = mapped_column(Integer)
    failed_login_attempts: Mapped[int] = mapped_column(Integer)
    location_category: Mapped[str] = mapped_column(String(30), default="office")
    application_usage: Mapped[str] = mapped_column(String(100), default="workstation")
    cpu_percent: Mapped[float] = mapped_column(Float, default=35)
    network_bytes_mb: Mapped[float] = mapped_column(Float, default=25)
    device_was_known: Mapped[bool] = mapped_column(Boolean, default=True)
    is_synthetic_anomaly: Mapped[bool] = mapped_column(Boolean, default=False)
    user: Mapped[User] = relationship(back_populates="events")
    device: Mapped[Device] = relationship(back_populates="events")
    prediction: Mapped[Prediction | None] = relationship(back_populates="event", uselist=False, cascade="all, delete-orphan")
    risk_score: Mapped[RiskScore | None] = relationship(back_populates="event", uselist=False, cascade="all, delete-orphan")
    anomaly: Mapped[Anomaly | None] = relationship(back_populates="event", uselist=False, cascade="all, delete-orphan")


class BehaviorBaseline(Base):
    __tablename__ = "behavior_baselines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"), nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    mean_login_hour: Mapped[float] = mapped_column(Float, default=9.0)
    std_login_hour: Mapped[float] = mapped_column(Float, default=1.5)
    mean_session_minutes: Mapped[float] = mapped_column(Float, default=45.0)
    mean_files_accessed: Mapped[float] = mapped_column(Float, default=8.0)
    mean_action_count: Mapped[float] = mapped_column(Float, default=40.0)
    mean_network_mb: Mapped[float] = mapped_column(Float, default=30.0)
    usual_applications: Mapped[list[str]] = mapped_column(JSON, default=list)
    usual_locations: Mapped[list[str]] = mapped_column(JSON, default=list)
    usual_network_zones: Mapped[list[str]] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("behavior_events.id"), unique=True)
    model_name: Mapped[str] = mapped_column(String(50))
    classification: Mapped[str] = mapped_column(String(20))
    anomaly_score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    event: Mapped[BehaviorEvent] = relationship(back_populates="prediction")


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("behavior_events.id"), unique=True)
    detected: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[float] = mapped_column(Float)
    indicators: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    event: Mapped[BehaviorEvent] = relationship(back_populates="anomaly")


class RiskScore(Base):
    __tablename__ = "risk_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("behavior_events.id"), unique=True)
    score: Mapped[int] = mapped_column(Integer)
    level: Mapped[str] = mapped_column(String(20))
    factors: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    event: Mapped[BehaviorEvent] = relationship(back_populates="risk_score")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("behavior_events.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    severity: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Investigation(Base):
    __tablename__ = "investigations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id"), index=True)
    analyst_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[str] = mapped_column(Text, default="")
    outcome: Mapped[str] = mapped_column(String(30), default="in_review")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class ModelMetric(Base):
    __tablename__ = "model_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_name: Mapped[str] = mapped_column(String(60), index=True)
    accuracy: Mapped[float] = mapped_column(Float)
    precision: Mapped[float] = mapped_column(Float)
    recall: Mapped[float] = mapped_column(Float)
    f1: Mapped[float] = mapped_column(Float)
    roc_auc: Mapped[float] = mapped_column(Float)
    confusion_matrix: Mapped[list[list[int]]] = mapped_column(JSON)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    user: Mapped[User] = relationship(back_populates="sessions")
