from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from config.settings import DATA_DIR, MODEL_DIR
from database.connection import SessionLocal
from database.init_db import initialize_database
from database.models import ModelMetric
from ml.preprocessing import preprocess_frame


def train_models(dataset_path: Path, model_dir: Path = MODEL_DIR, persist_metrics: bool = True) -> dict[str, dict[str, float | list[list[int]]]]:
    frame = pd.read_csv(dataset_path)
    features = preprocess_frame(frame)
    labels = frame["is_anomaly"].astype(int)
    x_train, x_test, y_train, y_test = train_test_split(features, labels, test_size=0.25, stratify=labels, random_state=42)
    positive_weight = max(1.0, (len(y_train) - int(y_train.sum())) / max(1, int(y_train.sum())))
    models = {
        "logistic_regression": LogisticRegression(max_iter=1200, class_weight="balanced", random_state=42),
        "random_forest": RandomForestClassifier(n_estimators=180, max_depth=12, min_samples_leaf=2, class_weight="balanced", n_jobs=-1, random_state=42),
        "xgboost": XGBClassifier(n_estimators=140, max_depth=4, learning_rate=0.08, subsample=0.9, colsample_bytree=0.9, scale_pos_weight=positive_weight, eval_metric="logloss", n_jobs=2, random_state=42),
    }
    model_dir.mkdir(parents=True, exist_ok=True)
    metrics: dict[str, dict[str, float | list[list[int]]]] = {}
    for name, model in models.items():
        model.fit(x_train, y_train)
        predicted = model.predict(x_test)
        probabilities = model.predict_proba(x_test)[:, 1]
        metrics[name] = _metrics(y_test, predicted, probabilities)
        joblib.dump(model, model_dir / f"{name}.joblib")

    forest = IsolationForest(n_estimators=200, contamination=float(labels.mean()), max_samples="auto", n_jobs=-1, random_state=42)
    forest.fit(x_train[y_train == 0])
    isolation_predictions = (forest.predict(x_test) == -1).astype(int)
    isolation_scores = -forest.decision_function(x_test)
    metrics["isolation_forest"] = _metrics(y_test, isolation_predictions, isolation_scores)
    joblib.dump(forest, model_dir / "isolation_forest.joblib")

    if persist_metrics:
        initialize_database()
        session = SessionLocal()
        try:
            for name, values in metrics.items():
                session.add(ModelMetric(model_name=name, **values))
            session.commit()
        finally:
            session.close()
    _write_report(metrics, model_dir.parent / "model_evaluation_report.md", len(frame), len(y_test))
    return metrics


def _metrics(actual: pd.Series, predicted: np.ndarray, scores: np.ndarray) -> dict[str, float | list[list[int]]]:
    return {
        "accuracy": round(float(accuracy_score(actual, predicted)), 4),
        "precision": round(float(precision_score(actual, predicted, zero_division=0)), 4),
        "recall": round(float(recall_score(actual, predicted, zero_division=0)), 4),
        "f1": round(float(f1_score(actual, predicted, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(actual, scores)), 4),
        "confusion_matrix": confusion_matrix(actual, predicted, labels=[0, 1]).tolist(),
    }


def _write_report(metrics: dict[str, dict[str, float | list[list[int]]]], path: Path, row_count: int, test_count: int) -> None:
    lines = ["# NeuroShield AI Model Evaluation", "", f"Synthetic events: {row_count:,}", f"Held-out test events: {test_count:,}", "", "| Model | Accuracy | Precision | Recall | F1 | ROC-AUC | Confusion matrix (normal/anomaly) |", "|---|---:|---:|---:|---:|---:|---|"]
    for name, values in metrics.items():
        matrix = values["confusion_matrix"]
        lines.append(f"| {name.replace('_', ' ').title()} | {values['accuracy']:.3f} | {values['precision']:.3f} | {values['recall']:.3f} | {values['f1']:.3f} | {values['roc_auc']:.3f} | `{matrix}` |")
    lines.extend(["", "All records are synthetic and generated from the documented simulation distributions. Scores are demonstration metrics, not production security guarantees.", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and compare NeuroShield anomaly classifiers.")
    parser.add_argument("--data", type=Path, default=DATA_DIR / "synthetic_behavior_data.csv")
    parser.add_argument("--model-dir", type=Path, default=MODEL_DIR)
    parser.add_argument("--no-db", action="store_true", help="Do not persist model metrics in the configured database.")
    args = parser.parse_args()
    metrics = train_models(args.data, args.model_dir, persist_metrics=not args.no_db)
    for name, values in metrics.items():
        print(f"{name:22} F1={values['f1']:.3f} ROC-AUC={values['roc_auc']:.3f}")
    print(f"Report saved to {args.model_dir.parent / 'model_evaluation_report.md'}")


if __name__ == "__main__":
    main()