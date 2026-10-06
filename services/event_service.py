from __future__ import annotations

import hashlib
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from database.crud import get_or_create_device
from database.models import Anomaly, BehaviorBaseline, BehaviorEvent, Prediction, RiskScore, User
from ml.anomaly_detection import detect_anomaly
from ml.classification import predict_risk
from services.alert_service import create_alert_if_needed
from ml.risk_engine import score_event


def baseline_for_user(session: Session, user_id: int, device_id: int | None = None) -> dict[str, Any]:
    if device_id is not None:
        baseline = session.scalar(select(BehaviorBaseline).where(BehaviorBaseline.user_id == user_id, BehaviorBaseline.device_id == device_id))
        if baseline is not None:
            return _baseline_dict(baseline)
        user_baseline = baseline_for_user(session, user_id)
        device_events = list(session.scalars(select(BehaviorEvent).where(
            BehaviorEvent.user_id == user_id,
            BehaviorEvent.device_id == device_id,
            BehaviorEvent.is_synthetic_anomaly.is_(False),
        ).order_by(BehaviorEvent.timestamp.desc()).limit(200)))
        if device_events:
            values = _summarize_events(device_events)
            session.add(BehaviorBaseline(user_id=user_id, device_id=device_id, sample_count=len(device_events), **values))
            session.flush()
            return values
        return user_baseline
    baseline = session.scalar(select(BehaviorBaseline).where(BehaviorBaseline.user_id == user_id, BehaviorBaseline.device_id.is_(None)))
    if baseline is not None:
        return _baseline_dict(baseline)
    events = list(session.scalars(select(BehaviorEvent).where(
        BehaviorEvent.user_id == user_id,
        BehaviorEvent.is_synthetic_anomaly.is_(False),
    ).order_by(BehaviorEvent.timestamp.desc()).limit(200)))
    if not events:
        return {"mean_login_hour": 9, "std_login_hour": 1.5, "mean_session_minutes": 45, "mean_files_accessed": 8, "mean_action_count": 40, "mean_network_mb": 30, "usual_applications": ["workstation", "browser", "analytics"], "usual_locations": ["office", "home", "remote"], "usual_network_zones": ["office", "home", "vpn"]}
    values = _summarize_events(events)
    session.add(BehaviorBaseline(user_id=user_id, sample_count=len(events), **values))
    session.flush()
    return values


def _summarize_events(events: list[BehaviorEvent]) -> dict[str, float]:
    count = len(events)
    angles = [event.login_hour * 2 * math.pi / 24 for event in events]
    mean_sin = sum(math.sin(angle) for angle in angles) / count
    mean_cos = sum(math.cos(angle) for angle in angles) / count
    mean_hour = math.atan2(mean_sin, mean_cos) % (2 * math.pi) * 24 / (2 * math.pi)
    concentration = max(1e-8, math.sqrt(mean_sin**2 + mean_cos**2))
    login_std = min(8.0, math.sqrt(-2 * math.log(concentration)) * 24 / (2 * math.pi))
    return {
        "mean_login_hour": mean_hour,
        "std_login_hour": max(1.0, login_std),
        "mean_session_minutes": sum(event.session_duration_minutes for event in events) / count,
        "mean_files_accessed": sum(event.files_accessed for event in events) / count,
        "mean_action_count": sum(event.action_count for event in events) / count,
        "mean_network_mb": sum(event.network_bytes_mb for event in events) / count,
        "usual_applications": [value for value, _ in Counter(event.application_usage for event in events).most_common()],
        "usual_locations": [value for value, _ in Counter(event.location_category for event in events).most_common()],
        "usual_network_zones": [value for value, _ in Counter(event.network_zone for event in events).most_common()],
    }


def _baseline_dict(baseline: BehaviorBaseline) -> dict[str, Any]:
    return {
        "mean_login_hour": baseline.mean_login_hour,
        "std_login_hour": baseline.std_login_hour,
        "mean_session_minutes": baseline.mean_session_minutes,
        "mean_files_accessed": baseline.mean_files_accessed,
        "mean_action_count": baseline.mean_action_count,
        "mean_network_mb": baseline.mean_network_mb,
        "usual_applications": baseline.usual_applications or [],
        "usual_locations": baseline.usual_locations or [],
        "usual_network_zones": baseline.usual_network_zones or [],
    }


def record_event(session: Session, user: User, payload: dict[str, Any], commit: bool = True) -> dict[str, Any]:
    device_key = str(payload.get("device_id", "SYNTH-DEVICE-01"))[:100]
    device = get_or_create_device(session, user.id, device_key)
    known_device = session.scalar(select(BehaviorEvent.id).where(BehaviorEvent.user_id == user.id, BehaviorEvent.device_id == device.id).limit(1)) is not None
    event_data = {**payload, "device_was_known": bool(payload.get("device_was_known", known_device))}
    now = datetime.now(timezone.utc)
    device.last_seen = now
    baseline = baseline_for_user(session, user.id, device.id)
    event = BehaviorEvent(
        user_id=user.id, device_id=device.id,
        timestamp=payload.get("timestamp", now),
        login_hour=float(event_data.get("login_hour", 9)),
        ip_address=str(event_data.get("ip_address", "192.0.2.10")),
        network_zone=str(event_data.get("network_zone", "office")),
        session_duration_minutes=float(event_data.get("session_duration_minutes", 45)),
        files_accessed=int(event_data.get("files_accessed", 8)),
        action_count=int(event_data.get("action_count", 40)),
        failed_login_attempts=int(event_data.get("failed_login_attempts", 0)),
        location_category=str(event_data.get("location_category", "office")),
        application_usage=str(event_data.get("application_usage", "workstation")),
        cpu_percent=float(event_data.get("cpu_percent", 35)),
        network_bytes_mb=float(event_data.get("network_bytes_mb", 30)),
        device_was_known=bool(event_data["device_was_known"]),
        is_synthetic_anomaly=bool(event_data.get("is_synthetic_anomaly", False)),
    )
    session.add(event)
    session.flush()
    features = {key: getattr(event, key) for key in (
        "login_hour", "session_duration_minutes", "files_accessed", "action_count", "failed_login_attempts",
        "network_bytes_mb", "cpu_percent", "network_zone", "location_category", "application_usage", "device_was_known",
    )}
    anomaly = detect_anomaly(features)
    prediction = predict_risk(features)
    risk = score_event(features, float(anomaly["score"]), baseline)
    explanation = {"risk": risk, "contributions": [{"label": label, "points": points} for label, points in risk["factors"].items()], "shap_values": {}}
    anomaly_record = Anomaly(event_id=event.id, detected=bool(anomaly["detected"]), score=float(anomaly["score"]), indicators=[item["label"] for item in explanation["contributions"]])
    prediction_record = Prediction(event_id=event.id, model_name=prediction["model_name"], classification=prediction["classification"], anomaly_score=float(anomaly["score"]), confidence=float(prediction["confidence"]))
    risk_record = RiskScore(event_id=event.id, score=int(risk["score"]), level=risk["level"], factors=risk["factors"])
    session.add_all([anomaly_record, prediction_record, risk_record])
    alert = create_alert_if_needed(session, event.id, user.username, int(risk["score"]), risk["level"], list(risk["factors"].keys()))
    if not event.is_synthetic_anomaly and int(risk["score"]) <= 25 and not anomaly["detected"]:
        _update_baseline(session, event)
    if commit:
        session.commit()
    else:
        session.flush()
    return {"event": event, "anomaly": anomaly_record, "prediction": prediction_record, "risk": risk_record, "alert": alert, "explanation": explanation, "baseline": baseline}


def _update_baseline(session: Session, event: BehaviorEvent) -> None:
    for device_id in (None, event.device_id):
        baseline = session.scalar(select(BehaviorBaseline).where(BehaviorBaseline.user_id == event.user_id, BehaviorBaseline.device_id == device_id))
        values = {
            "mean_login_hour": event.login_hour,
            "mean_session_minutes": event.session_duration_minutes,
            "mean_files_accessed": float(event.files_accessed),
            "mean_action_count": float(event.action_count),
            "mean_network_mb": event.network_bytes_mb,
        }
        if baseline is None:
            session.add(BehaviorBaseline(
                user_id=event.user_id, device_id=device_id, sample_count=1, std_login_hour=1.5,
                usual_applications=[event.application_usage], usual_locations=[event.location_category],
                usual_network_zones=[event.network_zone], **values,
            ))
            continue
        next_count = baseline.sample_count + 1
        login_delta = (event.login_hour - baseline.mean_login_hour + 12) % 24 - 12
        baseline.mean_login_hour = (baseline.mean_login_hour + login_delta / next_count) % 24
        baseline.std_login_hour = max(1.0, baseline.std_login_hour * 0.95 + abs(login_delta) * 0.05)
        for name in ("mean_session_minutes", "mean_files_accessed", "mean_action_count", "mean_network_mb"):
            setattr(baseline, name, getattr(baseline, name) + (values[name] - getattr(baseline, name)) / next_count)
        for name, value in (("usual_applications", event.application_usage), ("usual_locations", event.location_category), ("usual_network_zones", event.network_zone)):
            current = getattr(baseline, name) or []
            if value not in current:
                setattr(baseline, name, [*current, value])
        baseline.sample_count = next_count


def import_csv_events(session: Session, user: User, filename: str | Path, max_rows: int = 10_000) -> int:
    frame = pd.read_csv(filename, nrows=max_rows + 1).fillna(0)
    if frame.empty:
        raise ValueError("The selected CSV contains no events.")
    if len(frame) > max_rows:
        raise ValueError(f"CSV imports are limited to {max_rows:,} events at a time.")
    allowed = (
        "timestamp", "device_id", "login_hour", "session_duration_minutes", "files_accessed", "action_count",
        "failed_login_attempts", "location_category", "network_zone", "application_usage", "cpu_percent",
        "network_bytes_mb", "device_was_known",
    )
    imported = 0
    try:
        for row in frame.to_dict(orient="records"):
            payload = {key: row[key] for key in allowed if key in row}
            raw_device = str(payload.get("device_id", "SYN-DEVICE-01"))
            payload["device_id"] = f"CSV-DEVICE-{hashlib.sha256(raw_device.encode('utf-8')).hexdigest()[:16]}"
            payload["ip_address"] = "192.0.2.1"
            anomaly_label = row.get("is_anomaly", False)
            payload["is_synthetic_anomaly"] = anomaly_label.strip().lower() in {"1", "true", "yes"} if isinstance(anomaly_label, str) else bool(anomaly_label)
            if "timestamp" in payload:
                payload["timestamp"] = pd.to_datetime(payload["timestamp"], utc=True).to_pydatetime()
            record_event(session, user, payload, commit=False)
            imported += 1
        session.commit()
        return imported
    except Exception:
        session.rollback()
        raise


def load_investigation_event(session: Session, alert_id: int) -> tuple[Any, ...] | None:
    from database.models import Alert

    return session.execute(select(Alert, BehaviorEvent, User).join(BehaviorEvent, Alert.event_id == BehaviorEvent.id).join(User, BehaviorEvent.user_id == User.id).options(joinedload(BehaviorEvent.device)).where(Alert.id == alert_id)).first()