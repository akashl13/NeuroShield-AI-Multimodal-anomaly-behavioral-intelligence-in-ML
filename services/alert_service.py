from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from database.models import Alert, Investigation, User


def create_alert_if_needed(session: Session, event_id: int, username: str, score: int, level: str, reasons: list[str]) -> Alert | None:
    if score < 51:
        return None
    title = f"{level} behavioral risk detected"
    message = f"User {username} generated a risk score of {score}/100. " + (", ".join(reasons[:3]) or "Multiple behavioral signals exceeded baseline.")
    alert = Alert(event_id=event_id, title=title, severity=level, message=message, status="open")
    session.add(alert)
    session.flush()
    return alert


def mark_reviewed(session: Session, alert: Alert, analyst_id: int) -> None:
    alert.status = "investigating"
    alert.reviewed_by = analyst_id
    alert.reviewed_at = datetime.now(timezone.utc)
    investigation = session.query(Investigation).filter_by(alert_id=alert.id).first()
    if investigation is None:
        investigation = Investigation(alert_id=alert.id, analyst_id=analyst_id, outcome="in_review")
        session.add(investigation)
    session.commit()


def save_investigation(session: Session, alert: Alert, analyst_id: int, notes: str, resolve: bool = False) -> Investigation:
    investigation = session.query(Investigation).filter_by(alert_id=alert.id).first()
    if investigation is None:
        investigation = Investigation(alert_id=alert.id, analyst_id=analyst_id)
        session.add(investigation)
    investigation.analyst_id = analyst_id
    investigation.notes = notes.strip()
    investigation.outcome = "resolved" if resolve else "in_review"
    alert.status = "resolved" if resolve else "investigating"
    alert.reviewed_by = analyst_id
    alert.reviewed_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(investigation)
    return investigation


def update_alert_triage(session: Session, alert: Alert, status: str, assigned_to_id: int) -> Alert:
    normalized_status = status.strip().lower().replace(" ", "_")
    allowed_statuses = {"open", "acknowledged", "investigating", "resolved", "false_positive"}
    if normalized_status not in allowed_statuses:
        raise ValueError("Choose a supported alert status.")
    assignee = session.get(User, assigned_to_id)
    if assignee is None or not assignee.is_active or assignee.role not in {"admin", "analyst"}:
        raise ValueError("Choose an active analyst or administrator.")

    now = datetime.now(timezone.utc)
    alert.status = normalized_status
    alert.reviewed_by = assignee.id
    alert.reviewed_at = now
    investigation = session.query(Investigation).filter_by(alert_id=alert.id).first()
    if normalized_status == "investigating":
        if investigation is None:
            investigation = Investigation(alert_id=alert.id, analyst_id=assignee.id)
            session.add(investigation)
        investigation.analyst_id = assignee.id
        investigation.outcome = "in_review"
    elif investigation is not None and normalized_status in {"open", "resolved", "false_positive"}:
        investigation.outcome = "in_review" if normalized_status == "open" else normalized_status

    session.commit()
    session.refresh(alert)
    return alert