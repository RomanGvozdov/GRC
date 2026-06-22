from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user, require_admin
from app.database import get_db
from app.models import (
    Control,
    Framework,
    InformationSystem,
    ProfileType,
    ImplementationStatus,
    Requirement,
    User,
    effective_status_for_system,
)
from app.schemas import FrameworkOut, GapControl, GapRequirement, GapSummary, RequirementOut
from app.schemas_phase2 import FrameworkImportIn, FrameworkIn, RequirementIn
from app.services.audit import log_action

router = APIRouter(prefix="/frameworks", tags=["compliance"])


@router.get("", response_model=list[FrameworkOut])
def list_frameworks(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.scalars(select(Framework).order_by(Framework.id)).all()


@router.get("/{framework_id}/requirements", response_model=list[RequirementOut])
def list_requirements(
    framework_id: int,
    system_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if db.get(Framework, framework_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Фреймворк не знайдено")
    profile_type = None
    if system_id:
        system = db.get(InformationSystem, system_id)
        profile_type = system.profile_type if system else None
    requirements = db.scalars(
        select(Requirement).where(Requirement.framework_id == framework_id).order_by(Requirement.id)
    ).all()
    if profile_type:
        requirements = [r for r in requirements if requirement_applies(r, profile_type)]
    return [requirement_out(r, profile_type) for r in requirements]


@router.post("", response_model=FrameworkOut, status_code=status.HTTP_201_CREATED)
def create_framework(
    body: FrameworkIn, db: Session = Depends(get_db), actor: User = Depends(require_admin)
):
    """Створення кастомного каталогу (наприклад, для українських вимог)."""
    if db.scalar(select(Framework).where(Framework.code == body.code)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Фреймворк з таким кодом вже існує")
    framework = Framework(code=body.code, name=body.name, version=body.version, is_custom=True)
    db.add(framework)
    db.flush()
    log_action(db, actor, "create", "framework", framework.id, {"code": body.code})
    db.commit()
    return framework


@router.post("/import", response_model=FrameworkOut, status_code=status.HTTP_201_CREATED)
def import_framework(
    body: FrameworkImportIn, db: Session = Depends(get_db), actor: User = Depends(require_admin)
):
    """Імпорт каталогу разом із вимогами з JSON (повний NIST 800-53, НД ТЗІ тощо)."""
    if db.scalar(select(Framework).where(Framework.code == body.code)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Фреймворк з таким кодом вже існує")
    framework = Framework(code=body.code, name=body.name, version=body.version, is_custom=True)
    db.add(framework)
    db.flush()
    for req in body.requirements:
        db.add(
            Requirement(
                framework_id=framework.id,
                code=req.code,
                title=req.title,
                description=req.description,
                profile_types=_profiles_to_str(req.profiles),
            )
        )
    log_action(
        db, actor, "import", "framework", framework.id,
        {"code": body.code, "requirements": len(body.requirements)},
    )
    db.commit()
    return framework


_VALID_PROFILES = {p.value for p in ProfileType}


def _profiles_to_str(profiles: list[str]) -> str | None:
    for profile in profiles:
        if profile not in _VALID_PROFILES:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Невідомий профіль «{profile}» (допустимі: confidential, service)",
            )
    return ",".join(profiles) or None


def requirement_applies(requirement: Requirement, profile_type: str | None) -> bool:
    """Вимога застосовна до системи: без профілів — завжди; з профілями —
    лише якщо тип профілю системи входить у перелік."""
    if not requirement.profile_types:
        return True
    if not profile_type:
        return True  # система без типу профілю — показуємо все
    return profile_type in requirement.profile_types.split(",")


def requirement_out(requirement: Requirement, profile_type: str | None = None) -> RequirementOut:
    """RequirementOut із текстом під обраний профіль (якщо він відрізняється)."""
    out = RequirementOut.model_validate(requirement)
    if profile_type and requirement.profile_descriptions:
        specific = requirement.profile_descriptions.get(profile_type)
        if specific:
            out.description = specific
    return out


def _custom_framework(db: Session, framework_id: int) -> Framework:
    framework = db.get(Framework, framework_id)
    if framework is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Фреймворк не знайдено")
    if not framework.is_custom:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Вбудовані каталоги не можна редагувати"
        )
    return framework


@router.post(
    "/{framework_id}/requirements",
    response_model=RequirementOut,
    status_code=status.HTTP_201_CREATED,
)
def add_requirement(
    framework_id: int,
    body: RequirementIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    framework = _custom_framework(db, framework_id)
    requirement = Requirement(
        framework_id=framework.id,
        code=body.code,
        title=body.title,
        description=body.description,
        profile_types=_profiles_to_str(body.profiles),
    )
    db.add(requirement)
    db.flush()
    log_action(db, actor, "create", "requirement", requirement.id, {"code": body.code})
    db.commit()
    return requirement


@router.delete("/{framework_id}/requirements/{requirement_id}", status_code=204)
def delete_requirement(
    framework_id: int,
    requirement_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    _custom_framework(db, framework_id)
    requirement = db.get(Requirement, requirement_id)
    if requirement is None or requirement.framework_id != framework_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Вимогу не знайдено")
    log_action(db, actor, "delete", "requirement", requirement.id, {"code": requirement.code})
    db.delete(requirement)
    db.commit()


@router.delete("/{framework_id}", status_code=204)
def delete_framework(
    framework_id: int, db: Session = Depends(get_db), actor: User = Depends(require_admin)
):
    framework = _custom_framework(db, framework_id)
    log_action(db, actor, "delete", "framework", framework.id, {"code": framework.code})
    db.delete(framework)
    db.commit()


def requirement_coverage(requirement: Requirement, system_id: int | None = None) -> str:
    """Покриття вимоги контролями в контексті системи (None = вся організація)."""
    statuses = set()
    for control in requirement.controls:
        effective = effective_status_for_system(control.implementations, system_id)
        if effective is not None:
            statuses.add(effective)
    if not statuses:
        return "not_covered"
    if statuses == {ImplementationStatus.NOT_APPLICABLE.value}:
        return "not_applicable"
    if ImplementationStatus.IMPLEMENTED.value in statuses:
        return "covered"
    if ImplementationStatus.PARTIAL.value in statuses:
        return "partial"
    return "not_covered"


@router.get("/{framework_id}/gap-analysis", response_model=GapSummary)
def gap_analysis(
    framework_id: int,
    system_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    framework = db.get(Framework, framework_id)
    if framework is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Фреймворк не знайдено")

    profile_type = None
    if system_id:
        system = db.get(InformationSystem, system_id)
        profile_type = system.profile_type if system else None

    requirements = db.scalars(
        select(Requirement)
        .where(Requirement.framework_id == framework_id)
        .options(
            selectinload(Requirement.controls).selectinload(Control.implementations)
        )
        .order_by(Requirement.id)
    ).all()
    requirements = [r for r in requirements if requirement_applies(r, profile_type)]

    items: list[GapRequirement] = []
    counts = {"covered": 0, "partial": 0, "not_covered": 0, "not_applicable": 0}
    for requirement in requirements:
        coverage = requirement_coverage(requirement, system_id)
        counts[coverage] += 1
        items.append(
            GapRequirement(
                requirement=requirement_out(requirement, profile_type),
                controls=[
                    GapControl(
                        id=c.id, code=c.code, name=c.name,
                        status=effective_status_for_system(c.implementations, system_id),
                    )
                    for c in requirement.controls
                ],
                coverage=coverage,
            )
        )

    applicable = len(requirements) - counts["not_applicable"]
    percent = round(counts["covered"] / applicable * 100, 1) if applicable else 0.0
    return GapSummary(
        framework=FrameworkOut.model_validate(framework),
        total=len(requirements),
        covered=counts["covered"],
        partial=counts["partial"],
        not_covered=counts["not_covered"],
        not_applicable=counts["not_applicable"],
        coverage_percent=percent,
        requirements=items,
    )
