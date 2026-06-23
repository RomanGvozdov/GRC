"""AI-інфраструктура (ТЗ §9): провенанс AISuggestion + pgvector-сховище.

ai_suggestions — на обох діалектах (idempotent). ai_document_chunks і розширення
vector — лише PostgreSQL (на SQLite пропускається; AI у тестах вимкнено).
"""
import sqlalchemy as sa
from alembic import op

from app.config import get_settings

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "ai_suggestions" not in tables:
        op.create_table(
            "ai_suggestions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("kind", sa.String(32), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("model", sa.String(128), nullable=True),
            sa.Column("prompt_hash", sa.String(64), nullable=True),
            sa.Column("query", sa.Text(), nullable=True),
            sa.Column("output", sa.Text(), nullable=True),
            sa.Column("citations", sa.JSON(), nullable=True),
            sa.Column("accepted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        )

    # pgvector — лише PostgreSQL
    if bind.dialect.name == "postgresql":
        dim = get_settings().ai_embed_dim
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        if "ai_document_chunks" not in tables:
            op.execute(
                f"""
                CREATE TABLE ai_document_chunks (
                    id SERIAL PRIMARY KEY,
                    source_type VARCHAR(32) NOT NULL,
                    source_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    embedding vector({dim}) NOT NULL
                )
                """
            )
            op.execute(
                "CREATE INDEX ix_ai_chunks_source "
                "ON ai_document_chunks (source_type, source_id)"
            )
            op.execute(
                "CREATE INDEX ix_ai_chunks_embedding ON ai_document_chunks "
                "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TABLE IF EXISTS ai_document_chunks")
    insp = sa.inspect(bind)
    if "ai_suggestions" in insp.get_table_names():
        op.drop_table("ai_suggestions")
