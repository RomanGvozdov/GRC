"""SSP — план безпеки системи (RMF, ТЗ §6).

Генерація з резолвленого профілю, заповнення наративів, версіонування,
затвердження, експорт OSCAL/XLSX.
"""

import io
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, StreamingResponse
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user, require_admin
from app.database import get_db
from app.models import (
    InformationSystem,
    Profile,
    ProfileControl,
    SSP,
    SSPControl,
    SSPStatus,
    User,
)
from app.schemas import SSPControlIn, SSPControlOut, SSPDetailOut, SSPGenerateIn, SSPOut
from app.services.audit import log_action
from app.services.oscal import build_ssp_oscal

router = APIRouter(tags=["ssp"])

_SSP_LOAD = [selectinload(SSP.controls).selectinload(SSPControl.requirement),
             selectinload(SSP.controls).selectinload(SSPControl.responsible)]

_IMPL_UA = {
    "not_implemented": "Не впроваджено",
    "partial": "Частково",
    "implemented": "Впроваджено",
    "not_applicable": "Не застосовно",
}


def _ssp_out(ssp: SSP) -> SSPOut:
    out = SSPOut.model_validate(ssp)
    out.control_count = len(ssp.controls)
    out.implemented_count = sum(1 for c in ssp.controls if c.implementation_status == "implemented")
    return out


def _detail(db: Session, ssp_id: int) -> SSPDetailOut | None:
    ssp = db.scalar(select(SSP).where(SSP.id == ssp_id).options(*_SSP_LOAD))
    if ssp is None:
        return None
    base = _ssp_out(ssp)
    return SSPDetailOut(
        **base.model_dump(),
        controls=[SSPControlOut.model_validate(c) for c in ssp.controls],
    )


def _get_draft(db: Session, ssp_id: int) -> SSP:
    ssp = db.get(SSP, ssp_id)
    if ssp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SSP не знайдено")
    if ssp.status != SSPStatus.DRAFT.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "SSP не в статусі чернетки — створіть нову версію для змін",
        )
    return ssp


@router.post(
    "/systems/{system_id}/ssp",
    response_model=SSPDetailOut,
    status_code=status.HTTP_201_CREATED,
)
def generate_ssp(
    system_id: int,
    body: SSPGenerateIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    """Генерує SSP із цільового профілю: SSPControl на кожен включений контроль."""
    system = db.get(InformationSystem, system_id)
    if system is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Систему не знайдено")
    profile = db.scalar(
        select(Profile).where(Profile.id == body.profile_id)
        .options(selectinload(Profile.controls))
    )
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Профіль не знайдено")
    if profile.system_id != system_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Профіль належить іншій ІКС")

    ssp = SSP(
        system_id=system.id,
        profile_id=profile.id,
        title=body.title or f"SSP — {system.name}",
        version=1,
        status=SSPStatus.DRAFT.value,
        system_description=body.system_description or system.description,
    )
    db.add(ssp)
    db.flush()
    for pc in profile.controls:
        if pc.included:
            db.add(SSPControl(ssp_id=ssp.id, requirement_id=pc.requirement_id))
    log_action(
        db, actor, "create", "ssp", ssp.id,
        {"system": system.code, "profile_id": profile.id},
    )
    db.commit()
    return _detail(db, ssp.id)


@router.get("/systems/{system_id}/ssp", response_model=list[SSPOut])
def list_ssp(
    system_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    ssps = db.scalars(
        select(SSP).where(SSP.system_id == system_id)
        .options(selectinload(SSP.controls)).order_by(SSP.id)
    ).all()
    return [_ssp_out(s) for s in ssps]


@router.get("/ssp/{ssp_id}", response_model=SSPDetailOut)
def get_ssp(ssp_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    detail = _detail(db, ssp_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SSP не знайдено")
    return detail


@router.put("/ssp/{ssp_id}/controls/{requirement_id}", response_model=SSPDetailOut)
def update_ssp_control(
    ssp_id: int,
    requirement_id: int,
    body: SSPControlIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    """Опис впровадження та статус одного контролю SSP (лише чернетка)."""
    ssp = _get_draft(db, ssp_id)
    control = db.scalar(
        select(SSPControl).where(
            SSPControl.ssp_id == ssp.id, SSPControl.requirement_id == requirement_id
        )
    )
    if control is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Контроль не в SSP")
    if body.implementation_status is not None:
        control.implementation_status = body.implementation_status.value
    if body.narrative is not None:
        control.narrative = body.narrative
    control.responsible_id = body.responsible_id
    log_action(db, actor, "update", "ssp", ssp.id, {"requirement_id": requirement_id})
    db.commit()
    return _detail(db, ssp.id)


@router.post("/ssp/{ssp_id}/approve", response_model=SSPOut)
def approve_ssp(ssp_id: int, db: Session = Depends(get_db), actor: User = Depends(require_admin)):
    ssp = _get_draft(db, ssp_id)
    ssp.status = SSPStatus.APPROVED.value
    ssp.approved_at = datetime.now(timezone.utc)
    ssp.approved_by_id = actor.id
    log_action(db, actor, "approve", "ssp", ssp.id, {"version": ssp.version})
    db.commit()
    ssp = db.scalar(select(SSP).where(SSP.id == ssp_id).options(selectinload(SSP.controls)))
    return _ssp_out(ssp)


@router.post("/ssp/{ssp_id}/new-version", response_model=SSPDetailOut,
             status_code=status.HTTP_201_CREATED)
def new_ssp_version(
    ssp_id: int, db: Session = Depends(get_db), actor: User = Depends(require_admin)
):
    src = db.scalar(select(SSP).where(SSP.id == ssp_id).options(*_SSP_LOAD))
    if src is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SSP не знайдено")
    new = SSP(
        system_id=src.system_id,
        profile_id=src.profile_id,
        parent_ssp_id=src.id,
        title=src.title,
        version=src.version + 1,
        status=SSPStatus.DRAFT.value,
        system_description=src.system_description,
    )
    db.add(new)
    db.flush()
    for c in src.controls:
        db.add(SSPControl(
            ssp_id=new.id,
            requirement_id=c.requirement_id,
            implementation_status=c.implementation_status,
            narrative=c.narrative,
            responsible_id=c.responsible_id,
        ))
    src.status = SSPStatus.SUPERSEDED.value
    log_action(db, actor, "new_version", "ssp", new.id, {"from": src.id, "version": new.version})
    db.commit()
    return _detail(db, new.id)


@router.get("/ssp/{ssp_id}/oscal")
def export_ssp_oscal(
    ssp_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    ssp = db.scalar(select(SSP).where(SSP.id == ssp_id).options(*_SSP_LOAD))
    if ssp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SSP не знайдено")
    system = db.get(InformationSystem, ssp.system_id)
    doc = build_ssp_oscal(ssp, system, ssp.controls)
    return JSONResponse(
        doc,
        headers={
            "Content-Disposition": f'attachment; filename="ssp-{ssp_id}-oscal.json"'
        },
    )


@router.get("/ssp/{ssp_id}/export")
def export_ssp_xlsx(
    ssp_id: int,
    fmt: str = Query(default="xlsx", pattern="^xlsx$"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    ssp = db.scalar(select(SSP).where(SSP.id == ssp_id).options(*_SSP_LOAD))
    if ssp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SSP не знайдено")
    wb = Workbook()
    ws = wb.active
    ws.title = "SSP"
    ws.append(["Контроль", "Назва", "Статус впровадження", "Відповідальний", "Опис впровадження"])
    for c in ssp.controls:
        ws.append([
            c.requirement.code,
            c.requirement.title,
            _IMPL_UA.get(c.implementation_status, c.implementation_status),
            c.responsible.full_name if c.responsible else "",
            c.narrative or "",
        ])
    out = io.BytesIO()
    wb.save(out)
    filename = f"ssp-{ssp_id}_{date.today().isoformat()}.xlsx"
    return StreamingResponse(
        io.BytesIO(out.getvalue()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
