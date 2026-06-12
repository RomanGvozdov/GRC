"""Міграція даних зі схеми до впровадження ІКС (Фаза 4).

Виконується при старті після create_all. На свіжій БД нічого не робить.
На БД зі старою схемою (статус впровадження в controls, evidence.control_id):
1) кожен контроль отримує одне впровадження «вся організація» зі старими полями;
2) докази перев'язуються на ці впровадження;
3) застарілі колонки видаляються.
"""

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

_LEGACY_CONTROL_COLUMNS = [
    "implementation_status",
    "na_justification",
    "review_period_months",
    "next_review_date",
]


def migrate_legacy_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    control_cols = {c["name"] for c in inspector.get_columns("controls")}
    evidence_cols = {c["name"] for c in inspector.get_columns("evidence")}

    if "implementation_status" not in control_cols and "control_id" not in evidence_cols:
        return  # схема вже актуальна

    logger.info("Виявлено стару схему контролів — мігрую дані у впровадження")
    with engine.begin() as conn:
        if "implementation_status" in control_cols:
            conn.execute(text(
                "INSERT INTO control_implementations "
                "(control_id, system_id, implementation_status, na_justification, "
                " review_period_months, next_review_date, created_at, updated_at) "
                "SELECT id, NULL, implementation_status, na_justification, "
                "       review_period_months, next_review_date, "
                "       CURRENT_TIMESTAMP, CURRENT_TIMESTAMP "
                "FROM controls"
            ))

        if "control_id" in evidence_cols:
            if "implementation_id" not in evidence_cols:
                conn.execute(text("ALTER TABLE evidence ADD COLUMN implementation_id INTEGER"))
            conn.execute(text(
                "UPDATE evidence SET implementation_id = ("
                "  SELECT ci.id FROM control_implementations ci "
                "  WHERE ci.control_id = evidence.control_id AND ci.system_id IS NULL)"
            ))
            conn.execute(text("ALTER TABLE evidence DROP COLUMN control_id"))

        if "implementation_status" in control_cols:
            for column in _LEGACY_CONTROL_COLUMNS:
                conn.execute(text(f"ALTER TABLE controls DROP COLUMN {column}"))
    logger.info("Міграцію завершено")
