"""Інкремент 1, зріз «Baseline + категоризація ІКС» (ТЗ §5).

Додає baselines + baseline_items (набори контролів над каталогом) та колонки
категоризації впливу до systems. Ідемпотентно (guard через inspect): на свіжій
БД таблиці/колонки вже створені baseline-ревізією 0001, на проді — додаються тут.
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "baselines" not in tables:
        op.create_table(
            "baselines",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("catalog_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("level", sa.String(16), nullable=False, server_default="custom"),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["catalog_id"], ["frameworks.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_baselines_catalog_id", "baselines", ["catalog_id"])

    if "baseline_items" not in tables:
        op.create_table(
            "baseline_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("baseline_id", sa.Integer(), nullable=False),
            sa.Column("requirement_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["baseline_id"], ["baselines.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["requirement_id"], ["requirements.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("baseline_id", "requirement_id", name="uq_baseline_requirement"),
        )
        op.create_index("ix_baseline_items_baseline_id", "baseline_items", ["baseline_id"])
        op.create_index(
            "ix_baseline_items_requirement_id", "baseline_items", ["requirement_id"]
        )

    sys_cols = {c["name"] for c in insp.get_columns("systems")}
    for col in ("impact_confidentiality", "impact_integrity", "impact_availability"):
        if col not in sys_cols:
            op.add_column("systems", sa.Column(col, sa.String(16), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    sys_cols = {c["name"] for c in insp.get_columns("systems")}
    for col in ("impact_availability", "impact_integrity", "impact_confidentiality"):
        if col in sys_cols:
            op.drop_column("systems", col)
    tables = set(insp.get_table_names())
    if "baseline_items" in tables:
        op.drop_table("baseline_items")
    if "baselines" in tables:
        op.drop_table("baselines")
