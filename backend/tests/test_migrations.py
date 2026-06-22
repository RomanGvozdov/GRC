"""Схема має бути під керуванням Alembic (а не create_all при старті)."""

from sqlalchemy import inspect, text

from app.database import engine


def test_schema_is_alembic_managed(client):
    """Після старту застосунку існує alembic_version із зафіксованою ревізією."""
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    assert "alembic_version" in tables, "Схема не під керуванням Alembic"
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version, "Ревізію Alembic не зафіксовано"
    # ключові таблиці на місці
    assert {"users", "frameworks", "requirements", "control_implementations"} <= tables
