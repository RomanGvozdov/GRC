import json
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import hash_password
from app.models import Framework, Requirement, RiskCategory, Role, User

logger = logging.getLogger(__name__)

DEFAULT_CATEGORIES = [
    "Інформаційна безпека",
    "Операційні",
    "Юридичні",
    "Фінансові",
    "Кадрові",
]


def seed_admin(db: Session) -> None:
    if db.scalar(select(User.id).limit(1)):
        return
    settings = get_settings()
    if not settings.admin_password:
        logger.warning(
            "БД порожня, але ADMIN_PASSWORD не задано — першого адміністратора не створено"
        )
        return
    db.add(
        User(
            email=settings.admin_email.lower(),
            full_name=settings.admin_full_name,
            hashed_password=hash_password(settings.admin_password),
            role=Role.ADMIN.value,
        )
    )
    db.commit()
    logger.info("Створено першого адміністратора: %s", settings.admin_email)


def seed_categories(db: Session) -> None:
    if db.scalar(select(RiskCategory.id).limit(1)):
        return
    for name in DEFAULT_CATEGORIES:
        db.add(RiskCategory(name=name))
    db.commit()


def seed_frameworks(db: Session) -> None:
    data_dir = Path(__file__).parent / "seed_data"
    for path in sorted(data_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if db.scalar(select(Framework.id).where(Framework.code == data["code"])):
            continue
        framework = Framework(
            code=data["code"],
            name=data["name"],
            version=data.get("version"),
            is_custom=data.get("is_custom", False),
        )
        db.add(framework)
        db.flush()
        for req in data["requirements"]:
            db.add(
                Requirement(
                    framework_id=framework.id,
                    code=req["code"],
                    title=req["title"],
                    description=req.get("description"),
                )
            )
        db.commit()
        logger.info("Імпортовано каталог %s (%d вимог)", data["name"], len(data["requirements"]))


def run_seed(db: Session) -> None:
    seed_admin(db)
    seed_categories(db)
    seed_frameworks(db)
