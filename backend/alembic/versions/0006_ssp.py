"""Інкремент 2, зріз «SSP» (ТЗ §6): план безпеки системи.

Додає ssps + ssp_controls і колонку control_implementations.narrative. Ідемпотентно
(guard через inspect): на свіжій БД таблиці/колонка вже створені baseline-ревізією 0001.
"""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "ssps" not in tables:
        op.create_table(
            "ssps",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("system_id", sa.Integer(), nullable=False),
            sa.Column("profile_id", sa.Integer(), nullable=True),
            sa.Column("parent_ssp_id", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
            sa.Column("system_description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("approved_by_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["system_id"], ["systems.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["parent_ssp_id"], ["ssps.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["approved_by_id"], ["users.id"], ondelete="SET NULL"),
        )
        op.create_index("ix_ssps_system_id", "ssps", ["system_id"])

    if "ssp_controls" not in tables:
        op.create_table(
            "ssp_controls",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("ssp_id", sa.Integer(), nullable=False),
            sa.Column("requirement_id", sa.Integer(), nullable=False),
            sa.Column(
                "implementation_status", sa.String(32), nullable=False,
                server_default="not_implemented",
            ),
            sa.Column("narrative", sa.Text(), nullable=True),
            sa.Column("responsible_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["ssp_id"], ["ssps.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["requirement_id"], ["requirements.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["responsible_id"], ["users.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("ssp_id", "requirement_id", name="uq_ssp_requirement"),
        )
        op.create_index("ix_ssp_controls_ssp_id", "ssp_controls", ["ssp_id"])
        op.create_index(
            "ix_ssp_controls_requirement_id", "ssp_controls", ["requirement_id"]
        )

    impl_cols = {c["name"] for c in insp.get_columns("control_implementations")}
    if "narrative" not in impl_cols:
        op.add_column(
            "control_implementations", sa.Column("narrative", sa.Text(), nullable=True)
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    impl_cols = {c["name"] for c in insp.get_columns("control_implementations")}
    if "narrative" in impl_cols:
        op.drop_column("control_implementations", "narrative")
    tables = set(insp.get_table_names())
    for table in ("ssp_controls", "ssps"):
        if table in tables:
            op.drop_table(table)
