# NeuroShield AI

![NeuroShield banner](assets/neuroshield-banner.svg)

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/PySide6-Desktop%20UI-41CD52?logo=qt&logoColor=white)](https://pypi.org/project/PySide6/)
[![SQLite](https://img.shields.io/badge/DB-SQLite%20%7C%20Neon-6A5ACD)](https://www.sqlite.org/)
[![Status](https://img.shields.io/badge/Status-Demo%20%26%20Research-orange)](https://github.com/akashl13/NeuroShield-AI-Multimodal-anomaly-behavioral-intelligence-in-ML)

A modern behavioral intelligence platform for detecting risky user activity, surfacing explainable alerts, and supporting analyst investigations in a desktop security operations workflow.

## Overview

NeuroShield AI is a defensive analytics application designed to model normal user behavior, identify suspicious activity patterns, and assign a transparent risk score from 0 to 100. It combines behavioral telemetry, ML-based anomaly detection, and analyst-facing investigation views into a single operational dashboard.

This project is built for demo, training, and research use. It treats telemetry as synthetic or anonymized data and focuses on explainability, analyst workflow, and visibility into risk posture rather than production surveillance.

## Why this project matters

Traditional monitoring systems often surface raw logs without context. NeuroShield AI adds a human-centered layer:

- behavioral baselines for each user and device
- anomaly detection across login, session, and application usage patterns
- explainable risk scoring with traceable contributing factors
- alert triage and investigation workflows for analysts
- model comparison and dashboard analytics for operational review

## Key capabilities

- Secure local authentication with bcrypt password hashing and role-based access
- SQLite-first configuration with PostgreSQL/Neon support via `DATABASE_URL`
- Synthetic event simulation and CSV import for realistic demo data
- Machine learning workflows covering Isolation Forest, Logistic Regression, Random Forest, and XGBoost
- Dashboard metrics for users, events, anomalies, alerts, and investigation workload
- Searchable event review, alert triage, and investigation records tied to behavioral signals
- Explainable risk outputs that highlight the main behavioral contributors behind a score

## Tech stack

- Python 3.11+
- PySide6 for the desktop application interface
- SQLAlchemy + PostgreSQL/SQLite for persistence
- scikit-learn, XGBoost, pandas, and numpy for ML workflows
- dotenv for configuration
- Joblib for model artifact persistence

## Architecture

```mermaid
flowchart LR
    UI[PySide6 UI] --> Services[Auth / Event / Alert / Simulation Services]
    Services --> ORM[SQLAlchemy ORM]
    ORM --> DB[(SQLite or Neon PostgreSQL)]
    Services --> ML[Behavioral scoring and model inference]
    ML --> Artifacts[Model artifacts / metrics]
    DB --> UI
```

## Quick start

### Prerequisites

- Python 3.11 or later
- Linux desktop or graphical environment for the app UI
- Optional: Codespaces with browser-based VNC/noVNC access

### Install

```bash
sudo apt-get update
sudo apt-get install -y libgl1 libegl1 libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 libxcb-shape0
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

### Configure database

Use local SQLite by leaving `DATABASE_URL` unset, or point to Neon/PostgreSQL with a real connection string:

```dotenv
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require
```

Keep your credentials in the ignored `.env` file and never commit them to version control.

### Run the project

```bash
python -m database.init_db
python data/generate_synthetic.py
python -m ml.train
python -m pytest -q
python app.py
```

To create the first admin user from the terminal:

```bash
python app.py --create-user admin
```

The first registered account becomes the administrator. Additional registered accounts are treated as analysts.

## Browser deployment

For a browser-accessible desktop experience in a Linux-based environment, use:

```bash
bash run_desktop_browser.sh
```

This starts the virtual display and noVNC bridge so the app can be accessed through a browser on a remote device or Codespaces port-forwarded URL.

## Demo workflow

From the application UI, users can:

- log in with a created account
- load synthetic demo events
- review behavior events by risk level and timing
- investigate alert records
- compare model performance and anomaly trends
- regenerate data and retrain the model from settings

## Project structure

```text
app.py                 Main desktop application entry point
config/                Environment settings and configuration
database/              SQLAlchemy models, session setup, and DB utilities
gui/                   Login, dashboard, alerts, investigations, analytics, and settings screens
ml/                    Data pipeline, detection, model training, and evaluation
services/              Authentication, event scoring, simulation, and alert logic
data/                  Synthetic data generator and sample datasets
tests/                 Automated workflow and model validation checks
run_desktop_browser.sh Browser access helper for remote environments
```

## Model and evaluation workflow

The model training pipeline reads the synthetic behavior dataset, trains multiple classifiers, saves artifacts under `ml/models/`, and writes a report to `ml/model_evaluation_report.md`.

This includes:

- accuracy
- precision
- recall
- F1 score
- ROC-AUC
- confusion matrix

The synthetic data is designed for demonstration and educational analysis. It is not intended to represent real-world production security telemetry or model performance guarantees.

## Security and limitations

- Passwords are stored as bcrypt hashes.
- Session tokens are hashed before persistence.
- User/device identifiers and IPs are anonymized in imported CSV data.
- The project is a defensive demo platform and is not a production monitoring system.
- Use a proper migration framework before applying this schema to a shared production database.

## Mission

NeuroShield AI demonstrates how behavioral baselines, explainable risk modeling, and analyst workflows can be combined into a practical security intelligence tool for learning, prototyping, and operational simulation.