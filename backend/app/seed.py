import json
import logging
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import hash_password
from app.models import (
    Baseline,
    BaselineItem,
    BaselineLevel,
    ControlParameter,
    Framework,
    ProfileControl,
    Requirement,
    RiskCategory,
    Role,
    User,
)

# Каталог НД ТЗІ з базовими профілями → відповідні baselines.
ND_TZI_CATALOG_CODE = "nd-tzi-3-6-006-24"
ND_TZI_BASELINES = [
    ("confidential", BaselineLevel.ND_CONFIDENTIAL, "НД ТЗІ — Конфіденційна інформація"),
    ("service", BaselineLevel.ND_SERVICE, "НД ТЗІ — Службова інформація (ДСК)"),
    ("registry", BaselineLevel.ND_REGISTRY,
     "НД ТЗІ — Галузевий профіль публічних електронних реєстрів"),
]

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


def _family_of(code: str) -> str | None:
    m = re.match(r"^([A-Za-z]{2})-", code or "")
    return m.group(1).upper() if m else None


def _parent_code(code: str) -> str:
    """Базовий контроль для посилення: AC-2(1) → AC-2."""
    return re.sub(r"\(\d+\)$", "", code or "")


def _load_requirements(db: Session, framework: Framework, requirements: list[dict]) -> None:
    """Створює вимоги каталогу, лінкує посилення (parent_id) та ODP-параметри."""
    params_by_code: dict[str, list[dict]] = {}
    for req in requirements:
        profiles = req.get("profiles") or []
        db.add(
            Requirement(
                framework_id=framework.id,
                code=req["code"],
                title=req["title"],
                description=req.get("description"),
                family=_family_of(req["code"]),
                profile_types=",".join(profiles) or None,
                profile_descriptions=req.get("profile_descriptions"),
            )
        )
        if req.get("parameters"):
            params_by_code[req["code"]] = req["parameters"]
    db.flush()
    by_code = {
        r.code: r.id
        for r in db.scalars(
            select(Requirement).where(Requirement.framework_id == framework.id)
        )
    }
    for code, rid in by_code.items():
        parent = _parent_code(code)
        if parent != code and parent in by_code:
            db.get(Requirement, rid).parent_id = by_code[parent]
    # ODP-параметри: org-defined (без default) + прописані значення (default_value)
    for code, params in params_by_code.items():
        for p in params:
            db.add(
                ControlParameter(
                    requirement_id=by_code[code],
                    key=p["key"],
                    label=p.get("label"),
                    default_value=p.get("default_value"),
                    constraints={"org_defined": bool(p.get("org_defined"))},
                )
            )


def _framework_in_use(db: Session, framework_id: int) -> bool:
    """Чи є профілі ІКС, що посилаються на вимоги каталогу (видалення зруйнує дані)."""
    return db.scalar(
        select(ProfileControl.id)
        .join(Requirement, ProfileControl.requirement_id == Requirement.id)
        .where(Requirement.framework_id == framework_id)
        .limit(1)
    ) is not None


def seed_frameworks(db: Session) -> None:
    data_dir = Path(__file__).parent / "seed_data"
    for path in sorted(data_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        existing = db.scalar(select(Framework).where(Framework.code == data["code"]))
        if existing:
            # Каталог наявний: оновлюємо лише якщо змінилася версія сід-файлу
            # і немає побудованих профілів (інакше можна зруйнувати дані користувача).
            if existing.version == data.get("version"):
                continue
            if _framework_in_use(db, existing.id):
                logger.warning(
                    "Каталог %s має нову версію (%s→%s), але на ньому вже є профілі — "
                    "оновіть вручну (видаліть старий каталог у UI)",
                    data["code"], existing.version, data.get("version"),
                )
                continue
            logger.info(
                "Оновлення каталогу %s: %s → %s", data["code"], existing.version,
                data.get("version"),
            )
            db.delete(existing)  # cascade: вимоги, baseline_items, baselines
            db.flush()
        framework = Framework(
            code=data["code"],
            name=data["name"],
            version=data.get("version"),
            is_custom=data.get("is_custom", False),
        )
        db.add(framework)
        db.flush()
        _load_requirements(db, framework, data["requirements"])
        db.commit()
        logger.info("Імпортовано каталог %s (%d вимог)", data["name"], len(data["requirements"]))


def seed_baselines(db: Session) -> None:
    """Перетворює базові профілі НД ТЗІ (за `Requirement.profile_types`) на baselines.

    Ідемпотентно: пропускає baseline, який уже існує для цього каталогу й рівня.
    """
    catalog = db.scalar(select(Framework).where(Framework.code == ND_TZI_CATALOG_CODE))
    if catalog is None:
        return
    requirements = db.scalars(
        select(Requirement).where(Requirement.framework_id == catalog.id)
    ).all()
    for profile, level, name in ND_TZI_BASELINES:
        exists = db.scalar(
            select(Baseline.id).where(
                Baseline.catalog_id == catalog.id, Baseline.level == level.value
            )
        )
        if exists:
            continue
        matching = [
            r for r in requirements
            if profile in (r.profile_types or "").split(",")
        ]
        if not matching:
            continue
        baseline = Baseline(
            catalog_id=catalog.id,
            name=name,
            level=level.value,
            description=f"Базовий профіль НД ТЗІ 3.6-006-24 ({name}).",
        )
        db.add(baseline)
        db.flush()
        for r in matching:
            db.add(BaselineItem(baseline_id=baseline.id, requirement_id=r.id))
        db.commit()
        logger.info("Створено baseline %s (%d заходів)", name, len(matching))


def seed_catalog_parameters(db: Session) -> None:
    """Бекфіл ODP-параметрів у наявні каталоги (ідемпотентно, без чіпання профілів).

    Потрібно, коли каталог уже засіяний і refresh пропущено (бо на ньому є профілі):
    параметри з seed-JSON додаються до вимог, де їх ще немає.
    """
    data_dir = Path(__file__).parent / "seed_data"
    for path in sorted(data_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        params_by_code = {
            r["code"]: r["parameters"] for r in data["requirements"] if r.get("parameters")
        }
        if not params_by_code:
            continue
        fw = db.scalar(select(Framework).where(Framework.code == data["code"]))
        if fw is None:
            continue
        added = 0
        for code, params in params_by_code.items():
            req = db.scalar(
                select(Requirement).where(
                    Requirement.framework_id == fw.id, Requirement.code == code
                )
            )
            if req is None:
                continue
            has = db.scalar(
                select(ControlParameter.id)
                .where(ControlParameter.requirement_id == req.id).limit(1)
            )
            if has:
                continue
            for p in params:
                db.add(ControlParameter(
                    requirement_id=req.id, key=p["key"], label=p.get("label"),
                    default_value=p.get("default_value"),
                    constraints={"org_defined": bool(p.get("org_defined"))},
                ))
                added += 1
        if added:
            db.commit()
            logger.info("Бекфіл ODP-параметрів для %s: +%d", data["code"], added)


def run_seed(db: Session) -> None:
    seed_admin(db)
    seed_categories(db)
    seed_frameworks(db)
    seed_baselines(db)
    seed_catalog_parameters(db)
