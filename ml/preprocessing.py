from __future__ import annotations

from typing import Any

import pandas as pd

FEATURE_COLUMNS = [
    "login_hour", "device_known", "session_duration_minutes", "files_accessed",
    "action_count", "failed_login_attempts", "network_bytes_mb", "cpu_percent",
    "network_zone_code", "location_code", "application_code",
]
NETWORK_CODES = {"office": 0, "home": 1, "vpn": 2, "public": 3, "unknown": 4}
LOCATION_CODES = {"office": 0, "home": 1, "remote": 2, "unfamiliar": 3, "unknown": 4}
APPLICATION_CODES = {"workstation": 0, "browser": 1, "analytics": 2, "admin_console": 3, "unknown": 4}


def preprocess_event(event: dict[str, Any] | Any) -> pd.DataFrame:
    if not isinstance(event, dict):
        event = {key: getattr(event, key) for key in FEATURE_COLUMNS if hasattr(event, key)}
    row = {
        "login_hour": event.get("login_hour", 9),
        "device_known": int(bool(event.get("device_was_known", event.get("device_known", True)))),
        "session_duration_minutes": event.get("session_duration_minutes", 45),
        "files_accessed": event.get("files_accessed", 8),
        "action_count": event.get("action_count", 40),
        "failed_login_attempts": event.get("failed_login_attempts", 0),
        "network_bytes_mb": event.get("network_bytes_mb", 30),
        "cpu_percent": event.get("cpu_percent", 35),
        "network_zone_code": NETWORK_CODES.get(str(event.get("network_zone", "office")).lower(), 4),
        "location_code": LOCATION_CODES.get(str(event.get("location_category", "office")).lower(), 4),
        "application_code": APPLICATION_CODES.get(str(event.get("application_usage", "workstation")).lower(), 4),
    }
    frame = pd.DataFrame([row], columns=FEATURE_COLUMNS).apply(pd.to_numeric, errors="coerce")
    return frame.fillna(0).astype(float)


def preprocess_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = pd.DataFrame(index=frame.index)
    for column in FEATURE_COLUMNS:
        if column in frame:
            result[column] = frame[column]
        elif column == "device_known" and "device_was_known" in frame:
            result[column] = frame["device_was_known"]
        elif column.endswith("_code"):
            source, mapping = {
                "network_zone_code": ("network_zone", NETWORK_CODES),
                "location_code": ("location_category", LOCATION_CODES),
                "application_code": ("application_usage", APPLICATION_CODES),
            }[column]
            result[column] = frame[source].astype(str).str.lower().map(mapping) if source in frame else 4
        else:
            result[column] = 0
    result["device_known"] = result["device_known"].astype(int)
    return result.apply(pd.to_numeric, errors="coerce").fillna(0).astype(float)