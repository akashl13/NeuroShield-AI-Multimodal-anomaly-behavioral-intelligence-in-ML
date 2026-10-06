from __future__ import annotations

import random
from datetime import datetime, timezone


def generate_behavior_event(username: str, suspicious: bool = False, seed: int | None = None) -> dict:
    rng = random.Random(seed)
    timestamp = datetime.now(timezone.utc)
    if suspicious:
        return {
            "timestamp": timestamp, "device_id": f"SYN-NEW-{rng.randrange(1000, 9999)}", "ip_address": f"198.51.100.{rng.randrange(1, 255)}",
            "login_hour": float(rng.choice([1, 2, 3, 4, 23])), "device_was_known": False,
            "session_duration_minutes": round(rng.uniform(160, 520), 1), "files_accessed": rng.randint(32, 68),
            "action_count": rng.randint(145, 280), "failed_login_attempts": rng.randint(3, 7),
            "location_category": "unfamiliar", "network_zone": "public", "application_usage": "admin_console",
            "cpu_percent": round(rng.uniform(70, 99), 1), "network_bytes_mb": round(rng.uniform(500, 1600), 1),
            "is_synthetic_anomaly": True,
        }
    return {
        "timestamp": timestamp, "device_id": f"SYN-{username[:24].upper()}-LAPTOP", "ip_address": f"192.0.2.{rng.randrange(1, 255)}",
        "login_hour": round(rng.gauss(9.5, 1.3), 1), "device_was_known": True,
        "session_duration_minutes": round(rng.gauss(48, 12), 1), "files_accessed": max(1, int(rng.gauss(8, 3))),
        "action_count": max(5, int(rng.gauss(42, 12))), "failed_login_attempts": rng.choices([0, 1], [0.95, 0.05])[0],
        "location_category": rng.choices(["office", "home", "remote"], [0.55, 0.3, 0.15])[0],
        "network_zone": rng.choices(["office", "home", "vpn"], [0.55, 0.3, 0.15])[0],
        "application_usage": rng.choices(["workstation", "browser", "analytics"], [0.5, 0.3, 0.2])[0],
        "cpu_percent": round(rng.gauss(35, 10), 1), "network_bytes_mb": round(rng.lognormvariate(3.3, 0.45), 1),
        "is_synthetic_anomaly": False,
    }