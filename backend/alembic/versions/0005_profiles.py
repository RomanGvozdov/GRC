"""Інкремент 1, зріз «Profile + tailoring» (ТЗ §5).

Цільові профілі ІКС, контролі профілю, рішення tailoring (з обов'язковим
обґрунтуванням), значення ODP-параметрів та overlays. Ідемпотентно (guard через
inspect): на свіжій БД таблиці вже створені baseline-ревізією 0001, на проді —
додаються тут.
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "profiles" not in tables:
        op.create_table(
            "profiles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("system_id", sa.Integer(), nullable=False),
            sa.Column("baseline_id", sa.Integer(), nullable=True),
            sa.Column("parent_profile_id", sa.Integer(), nullable=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("approved_by_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["system_id"], ["systems.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["baseline_id"], ["baselines.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["parent_profile_id"], ["profiles.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["approved_by_id"], ["users.id"], ondelete="SET NULL"),
        )
        op.create_index("ix_profiles_system_id", "profiles", ["system_id"])

    if "profile_controls" not in tables:
        op.create_table(
            "profile_controls",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("profile_id", sa.Integer(), nullable=False),
            sa.Column("requirement_id", sa.Integer(), nullable=False),
            sa.Column("included", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("origin", sa.String(16), nullable=False, server_default="baseline"),
            sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["requirement_id"], ["requirements.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("profile_id", "requirement_id", name="uq_profile_requirement"),
        )
        op.create_index("ix_profile_controls_profile_id", "profile_controls", ["profile_id"])
        op.create_index(
            "ix_profile_controls_requirement_id", "profile_controls", ["requirement_id"]
        )

    if "tailoring_decisions" not in tables:
        op.create_table(
            "tailoring_decisions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("profile_id", sa.Integer(), nullable=False),
            sa.Column("requirement_id", sa.Integer(), nullable=True),
            sa.Column("action", sa.String(16), nullable=False),
            sa.Column("justification", sa.Text(), nullable=False),
            sa.Column("parameter_id", sa.Integer(), nullable=True),
            sa.Column("value", sa.Text(), nullable=True),
            sa.Column("created_by_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["requirement_id"], ["requirements.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(
                ["parameter_id"], ["control_parameters.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        )
        op.create_index(
            "ix_tailoring_decisions_profile_id", "tailoring_decisions", ["profile_id"]
        )

    if "profile_parameter_values" not in tables:
        op.create_table(
            "profile_parameter_values",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("profile_id", sa.Integer(), nullable=False),
            sa.Column("parameter_id", sa.Integer(), nullable=False),
            sa.Column("value", sa.Text(), nullable=False),
            sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["parameter_id"], ["control_parameters.id"], ondelete="CASCADE"
            ),
            sa.UniqueConstraint("profile_id", "parameter_id", name="uq_profile_parameter"),
        )
        op.create_index(
            "ix_profile_parameter_values_profile_id",
            "profile_parameter_values",
            ["profile_id"],
        )

    if "overlays" not in tables:
        op.create_table(
            "overlays",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("catalog_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["catalog_id"], ["frameworks.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_overlays_catalog_id", "overlays", ["catalog_id"])

    if "overlay_items" not in tables:
        op.create_table(
            "overlay_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("overlay_id", sa.Integer(), nullable=False),
            sa.Column("requirement_id", sa.Integer(), nullable=False),
            sa.Column("action", sa.String(16), nullable=False),
            sa.ForeignKeyConstraint(["overlay_id"], ["overlays.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["requirement_id"], ["requirements.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("overlay_id", "requirement_id", name="uq_overlay_requirement"),
        )
        op.create_index("ix_overlay_items_overlay_id", "overlay_items", ["overlay_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    for table in (
        "overlay_items",
        "overlays",
        "profile_parameter_values",
        "tailoring_decisions",
        "profile_controls",
        "profiles",
    ):
        if table in tables:
            op.drop_table(table)
