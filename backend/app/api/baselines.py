"""Baselines — набори контролів над каталогом (RMF, ТЗ §5)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user, require_admin
from app.database import get_db
from app.models import Baseline, BaselineItem, Framework, Requirement, User
from app.schemas import BaselineDetailOut, BaselineIn, BaselineOut, RequirementBrief
from app.services.audit import log_action

router = APIRouter(prefix="/baselines", tags=["baselines"])


def _to_out(baseline: Baseline, item_count: int) -> BaselineOut:
    return BaselineOut(
        id=baseline.id,
        catalog_id=baseline.catalog_id,
        name=baseline.name,
        level=baseline.level,
        description=baseline.description,
        created_at=baseline.created_at,
        item_count=item_count,
    )


@router.get("", response_model=list[BaselineOut])
def list_baselines(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    counts = dict(
        db.execute(
            select(BaselineItem.baseline_id, func.count(BaselineItem.id)).group_by(
                BaselineItem.baseline_id
            )
        ).all()
    )
    baselines = db.scalars(select(Baseline).order_by(Baseline.id)).all()
    return [_to_out(b, counts.get(b.id, 0)) for b in baselines]


@router.post("", response_model=BaselineDetailOut, status_code=status.HTTP_201_CREATED)
def create_baseline(
    body: BaselineIn, db: Session = Depends(get_db), actor: User = Depends(require_admin)
):
    catalog = db.get(Framework, body.catalog_id)
    if catalog is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Каталог не знайдено")

    requirement_ids = list(dict.fromkeys(body.requirement_ids))  # унікальні, зі збереженням порядку
    if requirement_ids:
        valid = set(
            db.scalars(
                select(Requirement.id).where(
                    Requirement.id.in_(requirement_ids),
                    Requirement.framework_id == catalog.id,
                )
            ).all()
        )
        missing = [rid for rid in requirement_ids if rid not in valid]
        if missing:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Вимоги не належать каталогу: {missing}",
            )

    baseline = Baseline(
        catalog_id=catalog.id,
        name=body.name,
        level=body.level,
        description=body.description,
    )
    db.add(baseline)
    db.flush()
    for rid in requirement_ids:
        db.add(BaselineItem(baseline_id=baseline.id, requirement_id=rid))
    log_action(
        db, actor, "create", "baseline", baseline.id,
        {"name": baseline.name, "level": baseline.level, "items": len(requirement_ids)},
    )
    db.commit()
    return _detail(db, baseline.id)


@router.get("/{baseline_id}", response_model=BaselineDetailOut)
def get_baseline(
    baseline_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    detail = _detail(db, baseline_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Baseline не знайдено")
    return detail


def _detail(db: Session, baseline_id: int) -> BaselineDetailOut | None:
    baseline = db.scalar(
        select(Baseline)
        .where(Baseline.id == baseline_id)
        .options(selectinload(Baseline.items).selectinload(BaselineItem.requirement))
    )
    if baseline is None:
        return None
    items = [RequirementBrief.model_validate(i.requirement) for i in baseline.items]
    out = _to_out(baseline, len(items))
    return BaselineDetailOut(**out.model_dump(), items=items)
