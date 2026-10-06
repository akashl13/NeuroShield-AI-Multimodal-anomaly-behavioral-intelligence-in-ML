from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from database.models import Alert, Investigation


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