"""RAG-сховище на pgvector (ТЗ §9). Лише PostgreSQL із розширенням vector;
на SQLite (тести) недоступне. Доступ — через raw SQL, без додаткових пакетів.

Таблиця ai_document_chunks створюється Alembic-ревізією 0003 (Postgres-only),
тому її немає в SQLAlchemy-метаданих (щоб не ламати SQLite)."""

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def vector_ready(engine: Engine) -> bool:
    """Чи доступне сховище ембедінгів (Postgres + розширення + таблиця)."""
    if engine.dialect.name != "postgresql":
        return False
    try:
        with engine.connect() as conn:
            has_ext = conn.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            ).first()
            has_table = conn.execute(
                text("SELECT to_regclass('public.ai_document_chunks')")
            ).scalar()
        return bool(has_ext) and has_table is not None
    except Exception:
        logger.exception("Не вдалося перевірити готовність pgvector")
        return False


def _vec(embedding: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in embedding) + "]"


def upsert_chunk(
    engine: Engine, source_type: str, source_id: int, content: str, embedding: list[float]
) -> None:
    """Зберегти/оновити фрагмент джерела (контроль, політика…) з ембедінгом."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "DELETE FROM ai_document_chunks "
                "WHERE source_type = :st AND source_id = :sid"
            ),
            {"st": source_type, "sid": source_id},
        )
        conn.execute(
            text(
                "INSERT INTO ai_document_chunks (source_type, source_id, content, embedding) "
                "VALUES (:st, :sid, :content, CAST(:emb AS vector))"
            ),
            {"st": source_type, "sid": source_id, "content": content, "emb": _vec(embedding)},
        )


def search(engine: Engine, embedding: list[float], k: int = 5) -> list[dict]:
    """Семантичний пошук k найближчих фрагментів (косинусна відстань)."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT source_type, source_id, content, "
                "       1 - (embedding <=> CAST(:emb AS vector)) AS score "
                "FROM ai_document_chunks "
                "ORDER BY embedding <=> CAST(:emb AS vector) LIMIT :k"
            ),
            {"emb": _vec(embedding), "k": k},
        ).mappings().all()
    return [dict(r) for r in rows]
