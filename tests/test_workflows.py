from sqlalchemy import select
import pandas as pd

from database.models import Alert, BehaviorBaseline, BehaviorEvent, Investigation
from services.alert_service import mark_reviewed, save_investigation
from services.auth_service import register_user
from services.event_service import import_csv_events, record_event
from services.simulation_service import generate_behavior_event


def test_event_is_persisted_and_scored(db_session):
    user = register_user(db_session, "event-analyst", "a sufficiently long password")
    result = record_event(db_session, user, generate_behavior_event(user.username, suspicious=False, seed=21))
    stored = db_session.scalar(select(BehaviorEvent).where(BehaviorEvent.id == result["event"].id))
    assert stored is not None
    assert stored.risk_score is not None
    assert stored.prediction is not None
    assert stored.anomaly is not None


def test_normal_activity_updates_user_and_device_baselines(db_session):
    user = register_user(db_session, "baseline-analyst", "a sufficiently long password")
    payload = generate_behavior_event(user.username, suspicious=False, seed=21)
    payload.update(login_hour=9.5, session_duration_minutes=45, files_accessed=8, action_count=40, failed_login_attempts=0, network_zone="office", location_category="office", application_usage="workstation", cpu_percent=35, network_bytes_mb=30, device_was_known=True)
    result = record_event(db_session, user, payload)
    baselines = list(db_session.scalars(select(BehaviorBaseline).where(BehaviorBaseline.user_id == user.id)))
    assert result["risk"].score <= 25
    assert len(baselines) == 2
    assert all(baseline.sample_count == 1 for baseline in baselines)
    assert all("workstation" in baseline.usual_applications for baseline in baselines)


def test_database_connection_fixture_is_operational(db_session):
    assert db_session.execute(select(1)).scalar_one() == 1


def test_csv_import_anonymizes_identifiers_and_batches_events(db_session, tmp_path):
    user = register_user(db_session, "import-analyst", "a sufficiently long password")
    source = tmp_path / "source.csv"
    pd.DataFrame([
        {"timestamp": "2026-01-01T09:00:00Z", "user_id": "real-source-user", "device_id": "private-device-serial", "ip_address": "10.1.2.3", "login_hour": 9, "session_duration_minutes": 45, "files_accessed": 8, "action_count": 40, "failed_login_attempts": 0, "location_category": "office", "network_zone": "office", "application_usage": "workstation", "cpu_percent": 35, "network_bytes_mb": 30, "device_was_known": True, "is_anomaly": False},
        {"timestamp": "2026-01-01T10:00:00Z", "user_id": "real-source-user", "device_id": "private-device-serial", "ip_address": "10.1.2.3", "login_hour": 10, "session_duration_minutes": 45, "files_accessed": 8, "action_count": 40, "failed_login_attempts": 0, "location_category": "office", "network_zone": "office", "application_usage": "workstation", "cpu_percent": 35, "network_bytes_mb": 30, "device_was_known": True, "is_anomaly": False},
    ]).to_csv(source, index=False)
    assert import_csv_events(db_session, user, source) == 2
    events = list(db_session.scalars(select(BehaviorEvent).order_by(BehaviorEvent.id)))
    assert len(events) == 2
    assert all(event.user_id == user.id for event in events)
    assert all(event.ip_address == "192.0.2.1" for event in events)
    assert all(event.device.device_id.startswith("CSV-DEVICE-") for event in events)
    assert all("private-device-serial" not in event.device.device_id for event in events)


def test_suspicious_event_creates_alert_and_can_be_resolved(db_session):
    user = register_user(db_session, "alert-analyst", "a sufficiently long password")
    result = record_event(db_session, user, generate_behavior_event(user.username, suspicious=True, seed=5))
    assert result["alert"] is not None
    alert = db_session.get(Alert, result["alert"].id)
    mark_reviewed(db_session, alert, user.id)
    investigation = save_investigation(db_session, alert, user.id, "Reviewed synthetic demonstration activity.", resolve=True)
    db_session.refresh(alert)
    assert alert.status == "resolved"
    assert investigation.outcome == "resolved"
    assert db_session.scalar(select(Investigation).where(Investigation.alert_id == alert.id)).notes