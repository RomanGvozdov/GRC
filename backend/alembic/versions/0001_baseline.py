"""Базова схема Фаз 1-2.

Створює всі таблиці з поточних метаданих. На існуючій БД (розгорнутій до
впровадження Alembic) безпечна: create_all пропускає наявні таблиці.
Подальші зміни схеми — через `alembic revision --autogenerate`.
"""
from alembic import op

from app.database import Base
from app import models  # noqa: F401

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
