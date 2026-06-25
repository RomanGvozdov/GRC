"""Інкремент 2, зріз «POA&M» (ТЗ §6): план дій та контрольних точок.

Додає poam_items + poam_milestones. Ідемпотентно (guard через inspect).
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "poam_items" not in tables:
        op.create_table(
            "poam_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("system_id", sa.Integer(), nullable=False),
            sa.Column("requirement_id", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(500), nullable=False),
            sa.Column("weakness", sa.Text(), nullable=True),
            sa.Column("status", sa.String(16), nullable=False, server_default="open"),
            sa.Column("severity", sa.String(16), nullable=True),
            sa.Column("source", sa.String(16), nullable=False, server_default="manual"),
            sa.Column("responsible_id", sa.Integer(), nullable=True),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["system_id"], ["systems.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["requirement_id"], ["requirements.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["responsible_id"], ["users.id"], ondelete="SET NULL"),
        )
        op.create_index("ix_poam_items_system_id", "poam_items", ["system_id"])

    if "poam_milestones" not in tables:
        op.create_table(
            "poam_milestones",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("poam_item_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(500), nullable=False),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["poam_item_id"], ["poam_items.id"], ondelete="CASCADE"),
        )
        op.create_index(
            "ix_poam_milestones_poam_item_id", "poam_milestones", ["poam_item_id"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    for table in ("poam_milestones", "poam_items"):
        if table in tables:
            op.drop_table(table)
