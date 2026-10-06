from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{ROOT_DIR / 'neuroshield.db'}")
MODEL_DIR = Path(os.getenv("MODEL_DIR", ROOT_DIR / "ml" / "models"))
DATA_DIR = ROOT_DIR / "data"
SESSION_TTL_MINUTES = int(os.getenv("SESSION_TTL_MINUTES", "30"))
APP_NAME = "NEUROSHIELD AI"
