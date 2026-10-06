from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from config.settings import MODEL_DIR
from ml.preprocessing import FEATURE_COLUMNS, preprocess_event

_FALLBACK_MODEL: IsolationForest | None = None
_MODEL_CACHE: dict[str, tuple[int, IsolationForest]] = {}


def detect_anomaly(event: dict, model: IsolationForest | None = None) -> dict[str, float | bool]:
    global _FALLBACK_MODEL
    features = preprocess_event(event)
    if model is None:
        model_path = MODEL_DIR / "isolation_forest.joblib"
        if model_path.exists():
            import joblib

            modified = model_path.stat().st_mtime_ns
            cached = _MODEL_CACHE.get(str(model_path))
            if cached is None or cached[0] != modified:
                _MODEL_CACHE[str(model_path)] = (modified, joblib.load(model_path))
            model = _MODEL_CACHE[str(model_path)][1]
        else:
            if _FALLBACK_MODEL is None:
                rng = np.random.default_rng(42)
                reference = pd.DataFrame(np.column_stack([
                    rng.normal(9, 1.5, 600), np.ones(600), rng.normal(45, 12, 600).clip(5, 120),
                    rng.poisson(8, 600), rng.poisson(40, 600), np.zeros(600),
                    rng.lognormal(3.2, 0.55, 600), rng.normal(35, 12, 600).clip(1, 90),
                    rng.choice([0, 1, 2], 600), rng.choice([0, 1, 2], 600), rng.choice([0, 1, 2], 600),
                ]), columns=FEATURE_COLUMNS)
                _FALLBACK_MODEL = IsolationForest(n_estimators=160, contamination=0.05, random_state=42).fit(reference)
            model = _FALLBACK_MODEL
    decision = float(model.decision_function(features)[0])
    normalized = float(np.clip((0.08 - decision) * 400 + 30, 0, 100))
    return {"detected": bool(model.predict(features)[0] == -1), "score": round(normalized, 1), "decision": decision}