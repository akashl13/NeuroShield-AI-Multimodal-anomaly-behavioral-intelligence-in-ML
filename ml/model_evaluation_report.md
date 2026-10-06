# NeuroShield AI Model Evaluation

Synthetic events: 2,400
Held-out test events: 600

| Model | Accuracy | Precision | Recall | F1 | ROC-AUC | Confusion matrix (normal/anomaly) |
|---|---:|---:|---:|---:|---:|---|
| Logistic Regression | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | `[[462, 0], [0, 138]]` |
| Random Forest | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | `[[462, 0], [0, 138]]` |
| Xgboost | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | `[[462, 0], [0, 138]]` |
| Isolation Forest | 0.817 | 0.556 | 1.000 | 0.715 | 1.000 | `[[352, 110], [0, 138]]` |

All records are synthetic and generated from the documented simulation distributions. Scores are demonstration metrics, not production security guarantees.
