from __future__ import annotations

from typing import Any


def score_event(event: dict[str, Any] | Any, anomaly_score: float = 0.0, baseline: dict[str, float] | None = None) -> dict[str, Any]:
    if not isinstance(event, dict):
        event = {key: getattr(event, key) for key in (
            "login_hour", "device_was_known", "session_duration_minutes", "files_accessed",
            "action_count", "failed_login_attempts", "network_bytes_mb", "cpu_percent",
            "network_zone", "location_category",
        ) if hasattr(event, key)}
    baseline = baseline or {}
    factors: dict[str, int] = {}
    login_hour = float(event.get("login_hour", 9))
    mean_hour = float(baseline.get("mean_login_hour", 9))
    hour_distance = abs(login_hour - mean_hour)
    hour_distance = min(hour_distance, 24 - hour_distance)
    if hour_distance >= 5:
        factors["Unusual login time"] = 24
    elif hour_distance >= 3:
        factors["Login outside the usual window"] = 14

    if not bool(event.get("device_was_known", event.get("device_known", True))):
        factors["Unknown device"] = 21
    failures = int(event.get("failed_login_attempts", 0))
    if failures >= 4:
        factors["Multiple failed logins"] = 15
    elif failures >= 2:
        factors["Repeated failed logins"] = 9

    files = float(event.get("files_accessed", 0))
    if files >= max(30, float(baseline.get("mean_files_accessed", 8)) * 3):
        factors["High file activity"] = 18
    elif files >= max(20, float(baseline.get("mean_files_accessed", 8)) * 2):
        factors["Elevated file activity"] = 10

    actions = float(event.get("action_count", 0))
    if actions >= max(150, float(baseline.get("mean_action_count", 40)) * 3):
        factors["Unusual activity volume"] = 15
    elif actions >= max(100, float(baseline.get("mean_action_count", 40)) * 2):
        factors["Elevated activity volume"] = 8

    network = float(event.get("network_bytes_mb", 0))
    if network >= max(500, float(baseline.get("mean_network_mb", 30)) * 5):
        factors["Unusual network activity"] = 14
    network_zone = str(event.get("network_zone", "office")).lower()
    usual_network_zones = baseline.get("usual_network_zones", [])
    if network_zone in {"public", "unknown"}:
        factors["Untrusted network zone"] = 10
    elif usual_network_zones and network_zone not in usual_network_zones:
        factors["Unusual network zone"] = 8
    location = str(event.get("location_category", "office")).lower()
    usual_locations = baseline.get("usual_locations", [])
    if location == "unfamiliar" or (usual_locations and location not in usual_locations):
        factors["Unfamiliar location"] = 10
    application = str(event.get("application_usage", "workstation")).lower()
    usual_applications = baseline.get("usual_applications", [])
    if usual_applications and application not in usual_applications:
        factors["Unusual application access"] = 12
    if float(event.get("session_duration_minutes", 45)) >= 600:
        factors["Extended session duration"] = 8
    if float(event.get("cpu_percent", 35)) >= 95:
        factors["Unusual endpoint activity"] = 8
    if anomaly_score >= 70:
        factors["Isolation Forest anomaly signal"] = 10

    score = min(100, sum(factors.values()))
    level = "LOW" if score <= 25 else "MEDIUM" if score <= 50 else "HIGH" if score <= 75 else "CRITICAL"
    return {"score": score, "level": level, "factors": factors}