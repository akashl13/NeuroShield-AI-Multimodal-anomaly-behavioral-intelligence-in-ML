from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.connection import Base
from database import models  # noqa: F401


@pytest.fixture
def db_session(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    model_dir = tmp_path / "models"
    monkeypatch.setattr("ml.anomaly_detection.MODEL_DIR", model_dir)
    monkeypatch.setattr("ml.classification.MODEL_DIR", model_dir)
    yield session
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()