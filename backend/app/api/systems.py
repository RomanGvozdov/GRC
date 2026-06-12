from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user, require_admin
from app.database import get_db
from app.models import ControlImplementation, InformationSystem, User
from app.schemas_phase4 import SystemIn, SystemOut
from app.services.audit import log_action

router = APIRouter(prefix="/systems", tags=["systems"])


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
