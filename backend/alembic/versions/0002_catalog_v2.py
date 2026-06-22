"""Каталог 2.0: enhancements (parent_id), family, source, ODP-параметри.

Інкремент 1 ТЗ §5.2. Дельта поверх базової ревізії 0001.

Ідемпотентна: базова ревізія 0001 використовує create_all поточних моделей,
тому на свіжій БД нові колонки/таблиці вже створені — тут лише доповнюємо
наявні БД (зокрема розгорнутий прод), де їх ще немає.
"""
import re

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    is_sqlite = bind.dialect.name == "sqlite"

    fw_cols = {c["name"] for c in insp.get_columns("frameworks")}
    if "source" not in fw_cols:
        op.add_column(
            "frameworks",
            sa.Column("source", sa.String(16), nullable=False, server_default="manual"),
        )

    req_cols = {c["name"] for c in insp.get_columns("requirements")}
    req_indexes = {i["name"] for i in insp.get_indexes("requirements")}
    if "parent_id" not in req_cols:
        op.add_column("requirements", sa.Column("parent_id", sa.Integer(), nullable=True))
        if not is_sqlite:
            op.create_foreign_key(
                "fk_requirements_parent", "requirements", "requirements",
                ["parent_id"], ["id"], ondelete="CASCADE",
            )
    if "family" not in req_cols:
        op.add_column("requirements", sa.Column("family", sa.String(8), nullable=True))
    if "ix_requirements_parent_id" not in req_indexes:
        op.create_index("ix_requirements_parent_id", "requirements", ["parent_id"])
    if "ix_requirements_family" not in req_indexes:
        op.create_index("ix_requirements_family", "requirements", ["family"])

    if "control_parameters" not in insp.get_table_names():
        op.create_table(
            "control_parameters",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("requirement_id", sa.Integer(), nullable=False),
            sa.Column("key", sa.String(64), nullable=False),
            sa.Column("label", sa.String(500), nullable=True),
            sa.Column("guidance", sa.Text(), nullable=True),
            sa.Column("constraints", sa.JSON(), nullable=True),
            sa.Column("default_value", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["requirement_id"], ["requirements.id"], ondelete="CASCADE"),
        )
        op.create_index(
            "ix_control_parameters_requirement_id", "control_parameters", ["requirement_id"]
        )

    # Бекфіл family для вимог із NIST-подібним кодом (AC-2, AU-3, AC-2(1)...)
    rows = bind.execute(
        sa.text("SELECT id, code FROM requirements WHERE family IS NULL")
    ).fetchall()
    for rid, code in rows:
        m = re.match(r"^([A-Za-z]{2})-", code or "")
        if m:
            bind.execute(
                sa.text("UPDATE requirements SET family = :f WHERE id = :id"),
                {"f": m.group(1).upper(), "id": rid},
            )


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "control_parameters" in insp.get_table_names():
        op.drop_table("control_parameters")
    op.drop_column("requirements", "family")
    op.drop_column("requirements", "parent_id")
    op.drop_column("frameworks", "source")
