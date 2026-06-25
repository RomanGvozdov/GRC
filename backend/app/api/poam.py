"""POA&M — план дій та контрольних точок (RMF, ТЗ §6)."""

import io
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, StreamingResponse
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.frameworks import requirement_coverage
from app.core.deps import get_current_user, require_admin
from app.database import get_db
from app.models import (
    Control,
    InformationSystem,
    POAMItem,
    POAMMilestone,
    POAMSource,
    POAMStatus,
    Profile,
    ProfileControl,
    Requirement,
    User,
)
from app.schemas import (
    POAMFromProfileOut,
    POAMItemDetailOut,
    POAMItemIn,
    POAMItemOut,
    POAMItemUpdate,
    POAMMilestoneIn,
    POAMMilestoneOut,
    POAMMilestoneUpdate,
)
from app.services.audit import log_action
from app.services.oscal import build_poam_oscal

router = APIRouter(tags=["poam"])

_STATUS_UA = {
    "open": "Відкрито", "in_progress": "В роботі",
    "completed": "Виконано", "risk_accepted": "Ризик прийнято",
}
_SEVERITY_UA = {"low": "Низька", "medium": "Середня", "high": "Висока", "critical": "Критична"}


def _item_out(item: POAMItem) -> POAMItemOut:
    out = POAMItemOut.model_validate(item)
    out.milestone_count = len(item.milestones)
    out.milestone_done = sum(1 for m in item.milestones if m.completed)
    return out


def _detail(db: Session, item_id: int) -> POAMItemDetailOut | None:
    item = db.scalar(
        select(POAMItem).where(POAMItem.id == item_id).options(
            selectinload(POAMItem.milestones),
            selectinload(POAMItem.requirement),
            selectinload(POAMItem.responsible),
        )
    )
    if item is None:
        return None
    base = _item_out(item)
    return POAMItemDetailOut(
        **base.model_dump(),
        milestones=[POAMMilestoneOut.model_validate(m) for m in item.milestones],
    )


@router.get("/systems/{system_id}/poam", response_model=list[POAMItemOut])
def list_poam(
    system_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    items = db.scalars(
        select(POAMItem).where(POAMItem.system_id == system_id).options(
            selectinload(POAMItem.milestones),
            selectinload(POAMItem.requirement),
            selectinload(POAMItem.responsible),
        ).order_by(POAMItem.id)
    ).all()
    return [_item_out(i) for i in items]


@router.post("/systems/{system_id}/poam", response_model=POAMItemDetailOut,
             status_code=status.HTTP_201_CREATED)
def create_poam(
    system_id: int,
    body: POAMItemIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    if db.get(InformationSystem, system_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Систему не знайдено")
    item = POAMItem(
        system_id=system_id,
        requirement_id=body.requirement_id,
        title=body.title,
        weakness=body.weakness,
        severity=body.severity,
        responsible_id=body.responsible_id,
        due_date=body.due_date,
        source=POAMSource.MANUAL.value,
    )
    db.add(item)
    db.flush()
    log_action(db, actor, "create", "poam", item.id, {"title": item.title})
    db.commit()
    return _detail(db, item.id)


@router.post("/systems/{system_id}/poam/from-profile/{profile_id}",
             response_model=POAMFromProfileOut)
def poam_from_profile_gaps(
    system_id: int,
    profile_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    """Генерує пункти POA&M із прогалин: контролі профілю, що не покриті/частково
    покриті впровадженнями. Уникає дублів (пропускає, якщо вже є відкритий пункт)."""
    profile = db.scalar(
        select(Profile).where(Profile.id == profile_id).options(
            selectinload(Profile.controls)
            .selectinload(ProfileControl.requirement)
            .selectinload(Requirement.controls)
            .selectinload(Control.implementations)
        )
    )
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Профіль не знайдено")
    if profile.system_id != system_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Профіль належить іншій ІКС")

    open_reqs = set(db.scalars(
        select(POAMItem.requirement_id).where(
            POAMItem.system_id == system_id,
            POAMItem.status != POAMStatus.COMPLETED.value,
            POAMItem.requirement_id.isnot(None),
        )
    ).all())

    created, skipped = [], 0
    for pc in profile.controls:
        if not pc.included:
            continue
        req = pc.requirement
        coverage = requirement_coverage(req, system_id)
        if coverage not in ("not_covered", "partial"):
            continue
        if req.id in open_reqs:
            skipped += 1
            continue
        item = POAMItem(
            system_id=system_id,
            requirement_id=req.id,
            title=f"Прогалина: {req.code} {req.title}",
            weakness=(
                "Контроль не впроваджено." if coverage == "not_covered"
                else "Контроль впроваджено частково."
            ),
            status=POAMStatus.OPEN.value,
            source=POAMSource.FROM_GAP.value,
        )
        db.add(item)
        open_reqs.add(req.id)
        created.append(item)
    db.flush()
    log_action(db, actor, "from_gaps", "poam", profile.id, {"created": len(created)})
    db.commit()
    return POAMFromProfileOut(
        created=len(created), skipped=skipped,
        items=[_item_out(db.get(POAMItem, i.id)) for i in created],
    )


@router.get("/poam/{item_id}", response_model=POAMItemDetailOut)
def get_poam(item_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    detail = _detail(db, item_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пункт POA&M не знайдено")
    return detail


@router.patch("/poam/{item_id}", response_model=POAMItemDetailOut)
def update_poam(
    item_id: int,
    body: POAMItemUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    item = db.get(POAMItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пункт POA&M не знайдено")
    for field in ("title", "weakness", "status", "severity", "responsible_id", "due_date"):
        value = getattr(body, field)
        if value is not None:
            setattr(item, field, value)
    log_action(db, actor, "update", "poam", item.id, {"status": item.status})
    db.commit()
    return _detail(db, item.id)


@router.delete("/poam/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_poam(item_id: int, db: Session = Depends(get_db), actor: User = Depends(require_admin)):
    item = db.get(POAMItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пункт POA&M не знайдено")
    log_action(db, actor, "delete", "poam", item.id, {"title": item.title})
    db.delete(item)
    db.commit()


@router.post("/poam/{item_id}/milestones", response_model=POAMItemDetailOut,
             status_code=status.HTTP_201_CREATED)
def add_milestone(
    item_id: int,
    body: POAMMilestoneIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    item = db.get(POAMItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пункт POA&M не знайдено")
    db.add(POAMMilestone(poam_item_id=item.id, title=body.title, due_date=body.due_date))
    log_action(db, actor, "add_milestone", "poam", item.id, {"title": body.title})
    db.commit()
    return _detail(db, item.id)


@router.patch("/poam/milestones/{milestone_id}", response_model=POAMItemDetailOut)
def update_milestone(
    milestone_id: int,
    body: POAMMilestoneUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    m = db.get(POAMMilestone, milestone_id)
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Контрольну точку не знайдено")
    if body.title is not None:
        m.title = body.title
    if body.due_date is not None:
        m.due_date = body.due_date
    if body.completed is not None:
        m.completed = body.completed
        m.completed_at = datetime.now(timezone.utc) if body.completed else None
    db.commit()
    return _detail(db, m.poam_item_id)


@router.get("/systems/{system_id}/poam/oscal")
def export_poam_oscal(
    system_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    system = db.get(InformationSystem, system_id)
    if system is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Систему не знайдено")
    items = db.scalars(
        select(POAMItem).where(POAMItem.system_id == system_id).options(
            selectinload(POAMItem.milestones), selectinload(POAMItem.requirement)
        ).order_by(POAMItem.id)
    ).all()
    doc = build_poam_oscal(system, items)
    return JSONResponse(
        doc,
        headers={"Content-Disposition": f'attachment; filename="poam-{system_id}-oscal.json"'},
    )


@router.get("/systems/{system_id}/poam/export")
def export_poam_xlsx(
    system_id: int,
    fmt: str = Query(default="xlsx", pattern="^xlsx$"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if db.get(InformationSystem, system_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Систему не знайдено")
    items = db.scalars(
        select(POAMItem).where(POAMItem.system_id == system_id).options(
            selectinload(POAMItem.milestones),
            selectinload(POAMItem.requirement),
            selectinload(POAMItem.responsible),
        ).order_by(POAMItem.id)
    ).all()
    wb = Workbook()
    ws = wb.active
    ws.title = "POA&M"
    ws.append(["Контроль", "Недолік", "Статус", "Критичність", "Відповідальний",
               "Термін", "Контрольні точки"])
    for it in items:
        ws.append([
            it.requirement.code if it.requirement else "",
            it.title,
            _STATUS_UA.get(it.status, it.status),
            _SEVERITY_UA.get(it.severity or "", ""),
            it.responsible.full_name if it.responsible else "",
            it.due_date.isoformat() if it.due_date else "",
            "; ".join(f"{m.title}{'✓' if m.completed else ''}" for m in it.milestones),
        ])
    out = io.BytesIO()
    wb.save(out)
    filename = f"poam-{system_id}_{date.today().isoformat()}.xlsx"
    return StreamingResponse(
        io.BytesIO(out.getvalue()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
