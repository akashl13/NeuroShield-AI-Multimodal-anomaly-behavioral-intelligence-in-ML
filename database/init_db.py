from sqlalchemy import inspect, text

from database.connection import Base, engine
from database import models  # noqa: F401


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    existing = {column["name"] for column in inspect(engine).get_columns("behavior_baselines")}
    pattern_columns = ("usual_applications", "usual_locations", "usual_network_zones")
    with engine.begin() as connection:
        for column in pattern_columns:
            if column not in existing:
                connection.execute(text(f"ALTER TABLE behavior_baselines ADD COLUMN {column} JSON NOT NULL DEFAULT '[]'"))


if __name__ == "__main__":
    initialize_database()
    print("NeuroShield database initialized.")