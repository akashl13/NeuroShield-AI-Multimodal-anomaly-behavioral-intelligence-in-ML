from __future__ import annotations

from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from database.models import Alert, Anomaly, BehaviorEvent, Device, Investigation, User


def get_or_create_device(session: Session, user_id: int, device_key: str) -> Device:
    device = session.scalar(select(Device).where(Device.user_id == user_id, Device.device_id == device_key))
    if device is None:
        device = Device(device_id=device_key, user_id=user_id)
        try:
            with session.begin_nested():
                session.add(device)
                session.flush()
        except IntegrityError:
            device_key = f"U{user_id}-{device_key}"[:100]
            device = session.scalar(select(Device).where(Device.user_id == user_id, Device.device_id == device_key))
            if device is None:
                device = Device(device_id=device_key, user_id=user_id)
                session.add(device)
                session.flush()
    return device


def list_events(session: Session, limit: int = 250) -> list[BehaviorEvent]:
    return list(session.scalars(select(BehaviorEvent).options(joinedload(BehaviorEvent.device)).order_by(desc(BehaviorEvent.timestamp)).limit(limit)).unique())


def list_alerts(session: Session, limit: int = 250) -> list[Alert]:
    return list(session.scalars(select(Alert).order_by(desc(Alert.created_at)).limit(limit)))


def get_dashboard_stats(session: Session) -> dict[str, int | float]:
    from database.models import RiskScore

    score_stats = session.execute(select(func.count(RiskScore.id), func.coalesce(func.avg(RiskScore.score), 0))).one()
    return {
        "users": session.scalar(select(func.count(User.id))) or 0,
        "events": session.scalar(select(func.count(BehaviorEvent.id))) or 0,
        "anomalies": session.scalar(select(func.count(Anomaly.id)).where(Anomaly.detected.is_(True))) or 0,
        "critical_alerts": session.scalar(select(func.count(Alert.id)).where(Alert.severity == "CRITICAL", Alert.status != "resolved")) or 0,
        "average_risk": round(float(score_stats[1] or 0), 1),
    }


def get_investigation(session: Session, alert_id: int) -> Investigation | None:
    return session.scalar(select(Investigation).where(Investigation.alert_id == alert_id).order_by(desc(Investigation.updated_at)))