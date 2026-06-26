"""Інкремент 3 (ТЗ §7): оцінювання (800-53A) + ConMon-поля доказів.

assessments + assessment_results; розширення evidence (source, automated,
system_id, requirement_id; implementation_id → nullable для авто-доказів).
Ідемпотентно (guard через inspect). Зміна nullable — лише PostgreSQL (на свіжій
БД/SQLite колонка вже nullable через baseline create_all поточних моделей).
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "assessments" not in tables:
        op.create_table(
            "assessments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("system_id", sa.Integer(), nullable=False),
            sa.Column("profile_id", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("status", sa.String(16), nullable=False, server_default="planned"),
            sa.Column("assessor_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["system_id"], ["systems.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["assessor_id"], ["users.id"], ondelete="SET NULL"),
        )
        op.create_index("ix_assessments_system_id", "assessments", ["system_id"])

    if "assessment_results" not in tables:
        op.create_table(
            "assessment_results",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("assessment_id", sa.Integer(), nullable=False),
            sa.Column("requirement_id", sa.Integer(), nullable=False),
            sa.Column("result", sa.String(24), nullable=False, server_default="not_assessed"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("assessed_by_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["requirement_id"], ["requirements.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["assessed_by_id"], ["users.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("assessment_id", "requirement_id", name="uq_assessment_requirement"),
        )
        op.create_index(
            "ix_assessment_results_assessment_id", "assessment_results", ["assessment_id"]
        )

    ev_cols = {c["name"] for c in insp.get_columns("evidence")}
    if "source" not in ev_cols:
        op.add_column("evidence", sa.Column("source", sa.String(32), nullable=False,
                                            server_default="manual"))
    if "automated" not in ev_cols:
        op.add_column("evidence", sa.Column("automated", sa.Boolean(), nullable=False,
                                            server_default=sa.false()))
    if "system_id" not in ev_cols:
        op.add_column("evidence", sa.Column("system_id", sa.Integer(), nullable=True))
        op.create_index("ix_evidence_system_id", "evidence", ["system_id"])
        if bind.dialect.name == "postgresql":
            op.create_foreign_key(
                "fk_evidence_system", "evidence", "systems",
                ["system_id"], ["id"], ondelete="CASCADE",
            )
    if "requirement_id" not in ev_cols:
        op.add_column("evidence", sa.Column("requirement_id", sa.Integer(), nullable=True))
        op.create_index("ix_evidence_requirement_id", "evidence", ["requirement_id"])
        if bind.dialect.name == "postgresql":
            op.create_foreign_key(
                "fk_evidence_requirement", "evidence", "requirements",
                ["requirement_id"], ["id"], ondelete="SET NULL",
            )

    # implementation_id → nullable (для авто-доказів без впровадження). Лише Postgres:
    # на свіжій БД/SQLite колонка вже nullable (baseline create_all поточних моделей).
    if bind.dialect.name == "postgresql":
        op.alter_column("evidence", "implementation_id", existing_type=sa.Integer(),
                        nullable=True)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    ev_cols = {c["name"] for c in insp.get_columns("evidence")}
    if bind.dialect.name == "postgresql":
        for fk in ("fk_evidence_requirement", "fk_evidence_system"):
            try:
                op.drop_constraint(fk, "evidence", type_="foreignkey")
            except Exception:
                pass
    for col in ("requirement_id", "system_id", "automated", "source"):
        if col in ev_cols:
            op.drop_column("evidence", col)
    tables = set(insp.get_table_names())
    for table in ("assessment_results", "assessments"):
        if table in tables:
            op.drop_table(table)
