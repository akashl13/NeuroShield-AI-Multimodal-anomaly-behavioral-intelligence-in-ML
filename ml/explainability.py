from __future__ import annotations

from typing import Any

import numpy as np

from ml.preprocessing import FEATURE_COLUMNS, preprocess_event
from ml.risk_engine import score_event

_EXPLAINER_CACHE: dict[str, Any] = {}

FEATURE_LABELS = {
    "login_hour": "Login hour", "device_known": "Known device", "session_duration_minutes": "Session duration",
    "files_accessed": "Files accessed", "action_count": "Action volume", "failed_login_attempts": "Failed logins",
    "network_bytes_mb": "Network activity", "cpu_percent": "CPU activity", "network_zone_code": "Network zone",
    "location_code": "Location category", "application_code": "Application usage",
}


def explain_event(event: dict[str, Any], anomaly_score: float, baseline: dict[str, float] | None = None) -> dict[str, Any]:
    risk = score_event(event, anomaly_score, baseline)
    contributions = [{"label": label, "points": points} for label, points in sorted(risk["factors"].items(), key=lambda item: item[1], reverse=True)]
    shap_values: dict[str, float] = {}
    try:
        from config.settings import MODEL_DIR
        model_path = MODEL_DIR / "random_forest.joblib"
        if model_path.exists():
            import joblib
            import shap

            cache_key = f"{model_path}:{model_path.stat().st_mtime_ns}"
            if cache_key not in _EXPLAINER_CACHE:
                _EXPLAINER_CACHE[cache_key] = shap.TreeExplainer(joblib.load(model_path))
            explainer = _EXPLAINER_CACHE[cache_key]
            values = explainer.shap_values(preprocess_event(event))
            if isinstance(values, list):
                values = values[-1]
            values = np.asarray(values)
            if values.ndim == 3:
                values = values[:, :, -1]
            row = values[0] if values.ndim > 1 else values
            shap_values = {FEATURE_LABELS[name]: round(float(value), 4) for name, value in zip(FEATURE_COLUMNS, row)}
    except Exception:
        shap_values = {}
    return {"risk": risk, "contributions": contributions, "shap_values": shap_values}
