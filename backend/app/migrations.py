"""Запуск Alembic-міграцій із коду (при старті застосунку).

Замінює попередній підхід `create_all` + ручна авто-міграція: схема тепер
керується ревізіями Alembic. Базова ревізія (0001) використовує create_all,
тому безпечна як для порожньої БД, так і для вже розгорнутої (idempotent).
"""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parent.parent


def run_migrations() -> None:
    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")
    logger.info("Alembic: схема оновлена до head")
