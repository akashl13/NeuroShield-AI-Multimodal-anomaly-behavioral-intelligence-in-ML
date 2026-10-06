from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "synthetic_behavior_data.csv"


def generate_dataset(rows: int = 2400, seed: int = 42) -> pd.DataFrame:
    if rows < 100:
        raise ValueError("Generate at least 100 rows for a useful train/test split.")
    rng = np.random.default_rng(seed)
    anomalous = rng.random(rows) < 0.22
    data: dict[str, object] = {
        "timestamp": pd.date_range("2025-01-01", periods=rows, freq="15min").astype(str),
        "user_id": [f"SYN-USER-{index % 32 + 1:03d}" for index in range(rows)],
        "device_id": [f"SYN-DEVICE-{index % 48 + 1:03d}" for index in range(rows)],
        "ip_address": [f"192.0.2.{index % 254 + 1}" for index in range(rows)],
        "login_hour": np.where(anomalous, rng.choice([0, 1, 2, 3, 4, 23], rows), rng.normal(9.5, 1.8, rows).clip(6, 19)),
        "device_was_known": ~anomalous | (rng.random(rows) > 0.7),
        "session_duration_minutes": np.where(anomalous, rng.lognormal(4.5, 1.0, rows).clip(4, 720), rng.normal(48, 16, rows).clip(5, 150)),
        "files_accessed": np.where(anomalous, rng.poisson(34, rows), rng.poisson(8, rows)),
        "action_count": np.where(anomalous, rng.poisson(150, rows), rng.poisson(42, rows)),
        "failed_login_attempts": np.where(anomalous, rng.choice([0, 1, 2, 3, 4, 5, 7], rows, p=[.1, .1, .15, .2, .2, .15, .1]), rng.choice([0, 0, 0, 0, 1], rows)),
        "location_category": np.where(anomalous, rng.choice(["unfamiliar", "remote", "office"], rows, p=[.5, .3, .2]), rng.choice(["office", "home", "remote"], rows, p=[.55, .3, .15])),
        "network_zone": np.where(anomalous, rng.choice(["public", "unknown", "vpn", "office"], rows), rng.choice(["office", "home", "vpn"], rows)),
        "application_usage": rng.choice(["workstation", "browser", "analytics", "admin_console"], rows, p=[.5, .25, .2, .05]),
        "cpu_percent": np.where(anomalous, rng.normal(76, 19, rows).clip(10, 100), rng.normal(35, 13, rows).clip(2, 85)),
        "network_bytes_mb": np.where(anomalous, rng.lognormal(5.4, 1.2, rows).clip(1, 3000), rng.lognormal(3.3, .55, rows).clip(1, 250)),
        "is_anomaly": anomalous.astype(int),
    }
    frame = pd.DataFrame(data)
    return frame.sample(frac=1, random_state=seed).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate anonymized NeuroShield behavior telemetry.")
    parser.add_argument("--rows", type=int, default=2400)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    frame = generate_dataset(args.rows, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False)
    print(f"Generated {len(frame):,} synthetic events ({frame['is_anomaly'].sum():,} anomalous): {args.output}")


if __name__ == "__main__":
    main()