from sqlalchemy import select
import pandas as pd
from sqlalchemy.orm import joinedload

from database.crud import get_dashboard_stats, get_risk_distribution, list_event_page
from database.models import Alert, BehaviorBaseline, BehaviorEvent, Investigation
from services.alert_service import mark_reviewed, save_investigation, update_alert_triage
from services.auth_service import register_user
from services.event_service import import_csv_events, record_event
from services.simulation_service import generate_behavior_event, generate_demo_events


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


def test_alert_can_eager_load_event_for_investigation(db_session):
    user = register_user(db_session, "relationship-analyst", "a sufficiently long password")
    result = record_event(db_session, user, generate_behavior_event(user.username, suspicious=True, seed=5))

    alert = db_session.scalar(select(Alert).options(joinedload(Alert.event)).where(Alert.id == result["alert"].id))

    assert alert.event.id == result["event"].id


def test_alert_triage_persists_assignment_and_false_positive(db_session):
    analyst = register_user(db_session, "triage-owner", "a sufficiently long password")
    assignee = register_user(db_session, "triage-assignee", "a sufficiently long password")
    result = record_event(db_session, analyst, generate_behavior_event(analyst.username, suspicious=True, seed=5))
    alert = result["alert"]

    update_alert_triage(db_session, alert, "investigating", assignee.id)
    db_session.refresh(alert)
    investigation = db_session.scalar(select(Investigation).where(Investigation.alert_id == alert.id))
    assert alert.status == "investigating"
    assert alert.reviewed_by == assignee.id
    assert investigation.analyst_id == assignee.id

    update_alert_triage(db_session, alert, "false positive", assignee.id)
    db_session.refresh(alert)
    assert alert.status == "false_positive"
    assert investigation.outcome == "false_positive"
    assert get_dashboard_stats(db_session)["critical_alerts"] == 0


def test_dashboard_stats_count_only_active_investigations(db_session):
    user = register_user(db_session, "dashboard-analyst", "a sufficiently long password")
    assert get_dashboard_stats(db_session)["average_risk"] is None
    result = record_event(db_session, user, generate_behavior_event(user.username, suspicious=True, seed=5))
    alert = result["alert"]
    assert alert is not None

    mark_reviewed(db_session, alert, user.id)
    assert get_dashboard_stats(db_session)["investigations"] == 1
    assert sum(get_risk_distribution(db_session).values()) == 1
    assert get_dashboard_stats(db_session)["average_risk"] is not None

    save_investigation(db_session, alert, user.id, "Resolved after review.", resolve=True)
    assert get_dashboard_stats(db_session)["investigations"] == 0


def test_event_page_supports_search_and_stable_pagination(db_session):
    from datetime import datetime, timedelta, timezone

    user = register_user(db_session, "page-analyst", "a sufficiently long password")
    older = generate_behavior_event(user.username, suspicious=False, seed=1)
    older["timestamp"] = datetime.now(timezone.utc) - timedelta(hours=1)
    record_event(db_session, user, older)
    newer = generate_behavior_event(user.username, suspicious=True, seed=2)
    newer["timestamp"] = datetime.now(timezone.utc)
    record_event(db_session, user, newer)

    first_page, total = list_event_page(db_session, page=1, page_size=1)
    second_page, _ = list_event_page(db_session, page=2, page_size=1)
    matching, matching_total = list_event_page(db_session, search="SYN-NEW")

    assert total == 2
    assert first_page[0].timestamp > second_page[0].timestamp
    assert matching_total == 1
    assert matching[0].device.device_id.startswith("SYN-NEW-")


def test_demo_data_is_synthetic_varied_and_scoped_to_signed_in_user(db_session):
    user = register_user(db_session, "demo-analyst", "a sufficiently long password")
    other_user = register_user(db_session, "other-analyst", "a sufficiently long password")

    assert generate_demo_events(db_session, user, count=12) == 12

    events = list(db_session.scalars(select(BehaviorEvent).where(BehaviorEvent.user_id == user.id)))
    other_events = list(db_session.scalars(select(BehaviorEvent).where(BehaviorEvent.user_id == other_user.id)))
    assert len(events) == 12
    assert other_events == []
    assert sum(event.is_synthetic_anomaly for event in events) >= 3
    assert len({event.timestamp.date() for event in events}) > 1


def test_demo_data_rejects_unbounded_counts(db_session):
    user = register_user(db_session, "bounded-demo", "a sufficiently long password")

    try:
        generate_demo_events(db_session, user, count=101)
    except ValueError as exc:
        assert "between 1 and 100" in str(exc)
    else:
        raise AssertionError("An oversized demo dataset was accepted")

    assert db_session.scalar(select(BehaviorEvent.id).limit(1)) is None