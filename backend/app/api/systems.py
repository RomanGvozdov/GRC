from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user, require_admin
from app.database import get_db
from app.models import (
    Baseline,
    BaselineLevel,
    ControlImplementation,
    ImpactLevel,
    InformationSystem,
    ProfileType,
    User,
)
from app.schemas_phase4 import CategorizationIn, CategorizationOut, SystemIn, SystemOut
from app.services.audit import log_action

router = APIRouter(prefix="/systems", tags=["systems"])

_IMPACT_RANK = {ImpactLevel.LOW: 0, ImpactLevel.MODERATE: 1, ImpactLevel.HIGH: 2}
# Тип профілю НД ТЗІ → рівень baseline
_ND_PROFILE_TO_LEVEL = {
    ProfileType.CONFIDENTIAL: BaselineLevel.ND_CONFIDENTIAL,
    ProfileType.SERVICE: BaselineLevel.ND_SERVICE,
    ProfileType.REGISTRY: BaselineLevel.ND_REGISTRY,
}


def _next_code(db: Session) -> str:
    last_id = db.scalar(
        select(InformationSystem.id).order_by(InformationSystem.id.desc()).limit(1)
    ) or 0
    return f"SYS-{last_id + 1:03d}"


@router.get("", response_model=list[SystemOut])
def list_systems(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.scalars(
        select(InformationSystem)
        .options(selectinload(InformationSystem.owner))
        .order_by(InformationSystem.id)
    ).all()


@router.post("", response_model=SystemOut, status_code=status.HTTP_201_CREATED)
def create_system(
    body: SystemIn, db: Session = Depends(get_db), actor: User = Depends(require_admin)
):
    if db.scalar(select(InformationSystem).where(InformationSystem.name == body.name)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Система з такою назвою вже існує")
    system = InformationSystem(
        code=_next_code(db),
        name=body.name,
        description=body.description,
        owner_id=body.owner_id,
        criticality=body.criticality.value if body.criticality else None,
        profile_type=body.profile_type.value if body.profile_type else None,
        status=body.status.value,
    )
    db.add(system)
    db.flush()
    log_action(db, actor, "create", "system", system.id, {"code": system.code, "name": body.name})
    db.commit()
    return db.get(InformationSystem, system.id)


@router.put("/{system_id}", response_model=SystemOut)
def update_system(
    system_id: int,
    body: SystemIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    system = db.get(InformationSystem, system_id)
    if system is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Систему не знайдено")
    system.name = body.name
    system.description = body.description
    system.owner_id = body.owner_id
    system.criticality = body.criticality.value if body.criticality else None
    system.profile_type = body.profile_type.value if body.profile_type else None
    system.status = body.status.value
    log_action(db, actor, "update", "system", system.id, {"code": system.code})
    db.commit()
    return system


@router.put("/{system_id}/categorization", response_model=CategorizationOut)
def categorize_system(
    system_id: int,
    body: CategorizationIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    """Категоризація ІКС: рівні впливу C/I/A (FIPS-199) або тип профілю НД ТЗІ.

    Повертає запропонований baseline (human-in-the-loop — не застосовується
    автоматично; генерація профілю з нього — окремий крок)."""
    system = db.get(InformationSystem, system_id)
    if system is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Систему не знайдено")

    impacts = [body.impact_confidentiality, body.impact_integrity, body.impact_availability]
    has_impacts = any(i is not None for i in impacts)
    if not has_impacts and body.nd_profile_type is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Вкажіть рівні впливу C/I/A або тип профілю НД ТЗІ",
        )

    suggested_level: str | None = None
    overall: ImpactLevel | None = None

    if has_impacts:
        system.impact_confidentiality = (
            body.impact_confidentiality.value if body.impact_confidentiality else None
        )
        system.impact_integrity = (
            body.impact_integrity.value if body.impact_integrity else None
        )
        system.impact_availability = (
            body.impact_availability.value if body.impact_availability else None
        )
        present = [i for i in impacts if i is not None]
        overall = max(present, key=lambda i: _IMPACT_RANK[i])  # high-water-mark
        suggested_level = overall.value

    if body.nd_profile_type is not None:
        system.profile_type = body.nd_profile_type.value
        suggested_level = _ND_PROFILE_TO_LEVEL[body.nd_profile_type].value

    suggested = (
        db.scalar(select(Baseline).where(Baseline.level == suggested_level).order_by(Baseline.id))
        if suggested_level
        else None
    )

    log_action(
        db, actor, "categorize", "system", system.id,
        {"overall_impact": overall.value if overall else None,
         "profile_type": system.profile_type,
         "suggested_baseline_id": suggested.id if suggested else None},
    )
    db.commit()

    return CategorizationOut(
        system_id=system.id,
        impact_confidentiality=system.impact_confidentiality,
        impact_integrity=system.impact_integrity,
        impact_availability=system.impact_availability,
        profile_type=system.profile_type,
        overall_impact=overall,
        suggested_baseline_id=suggested.id if suggested else None,
        suggested_baseline_name=suggested.name if suggested else None,
    )


@router.delete("/{system_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_system(
    system_id: int, db: Session = Depends(get_db), actor: User = Depends(require_admin)
):
    system = db.get(InformationSystem, system_id)
    if system is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Систему не знайдено")
    in_use = db.scalar(
        select(ControlImplementation.id)
        .where(ControlImplementation.system_id == system_id)
        .limit(1)
    )
    if in_use:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Система має впровадження контролів. Спершу видаліть або перенесіть їх",
        )
    log_action(db, actor, "delete", "system", system.id, {"code": system.code})
    db.delete(system)
    db.commit()
