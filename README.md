# NEUROSHIELD AI

**Multimodal Behavioral Anomaly & Risk Intelligence System** is a defensive security analytics desktop application for synthetic/anonymized user and device telemetry. It establishes behavioral baselines, detects anomalous activity, calculates explainable 0-100 risk, and supports analyst alert investigations.

## Capabilities

- Local account registration and login with bcrypt password hashes, admin/analyst roles, hashed expiring sessions, and logout. The first registered account is administrator; later registrations are analysts. Passwords must be at least 10 characters.
- SQLAlchemy persistence for users, devices, events, user/device baselines, predictions, anomalies, risk scores, alerts, investigations, model metrics, and auth sessions. SQLite is the zero-configuration default; PostgreSQL/Neon is selected with `DATABASE_URL`.
- Synthetic normal/suspicious event simulation and CSV import. Imported device identifiers are irreversibly hashed, IP addresses are replaced with `192.0.2.1`, and imported user IDs are not retained.
- Isolation Forest inference, Logistic Regression/Random Forest/XGBoost comparison, risk bands, rule-factor explanations, and on-demand Random Forest SHAP attribution.
- Dashboard trends, event history, alert triage, investigation notes/resolution, model metrics, confusion matrices, data generation, and model training.

## Quick Start

Python 3.11 or later is required. On a Linux desktop or a Codespace configured with a graphical display/X11 forwarding, install Qt's system libraries and the Python dependencies:

```bash
sudo apt-get update
sudo apt-get install -y libgl1 libegl1 libxkbcommon-x11-0
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

To use local SQLite, leave `DATABASE_URL` unset in `.env`. To use Neon, set `DATABASE_URL` there to the Neon PostgreSQL connection string, including `sslmode=require`. Never put credentials in source control; `.env` is ignored by Git.

Run the complete local workflow from the repository root:

```bash
python -m database.init_db
python data/generate_synthetic.py
python -m ml.train
python -m pytest -q
python app.py
```

The first account can also be created before launching the GUI, with the password requested securely in the terminal:

```bash
python app.py --create-user admin
```

Alternatively, choose **Create an analyst account** in the login window. The first account is automatically an administrator. Generate demonstration events from **Events**; **Settings** lets administrators regenerate the training CSV and retrain the models. Import `data/synthetic_behavior_data.csv` from **Events** to load historical sample activity for the signed-in analyst.

### GitHub Codespaces

In a Codespace, run the setup commands above in the integrated terminal, then:

```bash
python -m database.init_db
python data/generate_synthetic.py
python -m ml.train
python -m pytest -q
python app.py
```

Codespaces does not provide a desktop display by default. The PySide6 window requires a configured remote desktop or X11 display; `QT_QPA_PLATFORM=offscreen` is suitable only for non-interactive widget smoke checks, not for using the application.

For Neon, set the real connection string in `.env` before initializing the database and training so model metrics are persisted to the selected database. Schema initialization uses SQLAlchemy `create_all` and is intended for a fresh demonstration database.

## Training And Evaluation

`python -m ml.train` reads `data/synthetic_behavior_data.csv`, stratifies a held-out test set, trains Logistic Regression, Random Forest, XGBoost, and Isolation Forest, saves Joblib artifacts under `ml/models/`, persists classification metrics, and writes `ml/model_evaluation_report.md`. The report includes accuracy, precision, recall, F1, ROC-AUC, and confusion matrices.

The supplied generator intentionally creates learnable synthetic anomalies. Its evaluation scores are demonstration results, not estimates of production security performance. The Isolation Forest also runs before training using a deterministic synthetic normal reference, so event scoring remains available before model artifacts exist.

## Structure

```text
app.py                 PySide6 entry point and account bootstrap
config/                Environment-driven settings
database/              SQLAlchemy models, session factory, initialization, CRUD
gui/                   Login, dashboard, events, alerts, investigations, analytics, settings
ml/                    Preprocessing, Isolation Forest, classifiers, risk, SHAP, training
data/                  Synthetic CSV and deterministic generator
services/              Authentication, event analysis, alert, and simulation workflows
tests/                 Isolated SQLite and behavioral workflow tests
```

All sample addresses use reserved documentation networks. This project does not collect host telemetry or perform surveillance, credential theft, exploitation, or system access. It is an educational defensive analytics demonstration and is not a replacement for an operational security monitoring system.