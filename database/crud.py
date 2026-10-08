from __future__ import annotations

from sqlalchemy import desc, func, or_, select
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


def list_event_page(
    session: Session,
    page: int = 1,
    page_size: int = 50,
    search: str = "",
    risk_level: str = "",
    anomaly_status: str = "",
    sort_by: str = "newest",
) -> tuple[list[BehaviorEvent], int]:
    from database.models import RiskScore

    page = max(1, page)
    page_size = min(100, max(1, page_size))
    filters = []
    if search.strip():
        pattern = f"%{search.strip()}%"
        filters.append(or_(
            BehaviorEvent.user.has(User.username.ilike(pattern)),
            BehaviorEvent.device.has(Device.device_id.ilike(pattern)),
            BehaviorEvent.application_usage.ilike(pattern),
            BehaviorEvent.network_zone.ilike(pattern),
        ))
    if risk_level:
        filters.append(BehaviorEvent.risk_score.has(RiskScore.level == risk_level.upper()))
    if anomaly_status == "anomalous":
        filters.append(BehaviorEvent.anomaly.has(Anomaly.detected.is_(True)))
    elif anomaly_status == "normal":
        filters.append(or_(
            BehaviorEvent.anomaly.has(Anomaly.detected.is_(False)),
            ~BehaviorEvent.anomaly.has(),
        ))

    total = session.scalar(select(func.count(BehaviorEvent.id)).where(*filters)) or 0
    statement = select(BehaviorEvent).options(
        joinedload(BehaviorEvent.user),
        joinedload(BehaviorEvent.device),
        joinedload(BehaviorEvent.risk_score),
        joinedload(BehaviorEvent.anomaly),
        joinedload(BehaviorEvent.prediction),
    ).where(*filters)
    if sort_by == "highest risk":
        statement = statement.outerjoin(RiskScore, RiskScore.event_id == BehaviorEvent.id).order_by(desc(func.coalesce(RiskScore.score, 0)), desc(BehaviorEvent.timestamp))
    elif sort_by == "oldest":
        statement = statement.order_by(BehaviorEvent.timestamp, BehaviorEvent.id)
    else:
        statement = statement.order_by(desc(BehaviorEvent.timestamp), desc(BehaviorEvent.id))
    events = list(session.scalars(statement.offset((page - 1) * page_size).limit(page_size)).unique())
    return events, int(total)


def list_alerts(session: Session, limit: int = 250) -> list[Alert]:
    return list(session.scalars(select(Alert).order_by(desc(Alert.created_at)).limit(limit)))


def get_dashboard_stats(session: Session) -> dict[str, int | float | None]:
    from database.models import RiskScore
    score_stats = session.execute(select(func.count(RiskScore.id), func.coalesce(func.avg(RiskScore.score), 0))).one()
    return {
        "users": session.scalar(select(func.count(User.id))) or 0,
        "events": session.scalar(select(func.count(BehaviorEvent.id))) or 0,
        "anomalies": session.scalar(select(func.count(Anomaly.id)).where(Anomaly.detected.is_(True))) or 0,
        "critical_alerts": session.scalar(select(func.count(Alert.id)).where(Alert.severity == "CRITICAL", Alert.status.in_(("open", "acknowledged", "investigating")))) or 0,
        "investigations": session.scalar(select(func.count(Investigation.id)).where(Investigation.outcome == "in_review")) or 0,
        "average_risk": round(float(score_stats[1]), 1) if score_stats[0] else None,
    }


def get_risk_distribution(session: Session) -> dict[str, int]:
    from database.models import RiskScore

    rows = session.execute(select(RiskScore.level, func.count(RiskScore.id)).group_by(RiskScore.level)).all()
    counts = {str(level).upper(): int(count) for level, count in rows}
    return {level: counts.get(level, 0) for level in ("LOW", "MEDIUM", "HIGH", "CRITICAL")}


def get_investigation(session: Session, alert_id: int) -> Investigation | None:
    return session.scalar(select(Investigation).where(Investigation.alert_id == alert_id).order_by(desc(Investigation.updated_at)))