from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib

from config.settings import MODEL_DIR
from ml.preprocessing import FEATURE_COLUMNS, preprocess_event

_MODEL_CACHE: dict[str, tuple[int, Any]] = {}


def predict_risk(event: dict[str, Any], model_name: str = "random_forest") -> dict[str, Any]:
    model_path = MODEL_DIR / f"{model_name}.joblib"
    if not model_path.exists():
        return {"classification": "anomalous" if _fallback_anomaly(event) else "normal", "confidence": 0.0, "model_name": "rule_fallback"}
    modified = model_path.stat().st_mtime_ns
    cached = _MODEL_CACHE.get(str(model_path))
    if cached is None or cached[0] != modified:
        _MODEL_CACHE[str(model_path)] = (modified, joblib.load(model_path))
    model = _MODEL_CACHE[str(model_path)][1]
    features = preprocess_event(event)
    prediction = int(model.predict(features)[0])
    probability = float(model.predict_proba(features)[0][1]) if hasattr(model, "predict_proba") else float(prediction)
    return {"classification": "anomalous" if prediction else "normal", "confidence": round(probability, 4), "model_name": model_name}


def _fallback_anomaly(event: dict[str, Any]) -> bool:
    return (
        not bool(event.get("device_was_known", True))
        or int(event.get("failed_login_attempts", 0)) >= 3
        or int(event.get("files_accessed", 0)) >= 25
        or float(event.get("login_hour", 9)) < 5
        or float(event.get("login_hour", 9)) > 23
    )