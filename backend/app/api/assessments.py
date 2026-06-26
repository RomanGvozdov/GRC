"""Оцінювання контролів (800-53A, RMF «Assess», ТЗ §7)."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user, require_admin
from app.database import get_db
from app.models import (
    Assessment,
    AssessmentResult,
    AssessmentResultValue,
    AssessmentStatus,
    InformationSystem,
    POAMItem,
    POAMSource,
    POAMStatus,
    Profile,
    ProfileControl,
    User,
)
from app.schemas import (
    AssessmentDetailOut,
    AssessmentGenerateIn,
    AssessmentOut,
    AssessmentResultIn,
    AssessmentResultOut,
    AssessmentUpdate,
    POAMFromProfileOut,
)
from app.api.poam import _item_out
from app.services.audit import log_action

router = APIRouter(tags=["assessments"])

_LOAD = [selectinload(Assessment.results).selectinload(AssessmentResult.requirement),
         selectinload(Assessment.assessor)]


def _out(a: Assessment) -> AssessmentOut:
    out = AssessmentOut.model_validate(a)
    out.total = len(a.results)
    out.satisfied = sum(1 for r in a.results if r.result == "satisfied")
    out.other_than_satisfied = sum(1 for r in a.results if r.result == "other_than_satisfied")
    out.not_assessed = sum(1 for r in a.results if r.result == "not_assessed")
    return out


def _detail(db: Session, aid: int) -> AssessmentDetailOut | None:
    a = db.scalar(select(Assessment).where(Assessment.id == aid).options(*_LOAD))
    if a is None:
        return None
    base = _out(a)
    return AssessmentDetailOut(
        **base.model_dump(),
        results=[AssessmentResultOut.model_validate(r) for r in a.results],
    )


@router.post("/systems/{system_id}/assessments", response_model=AssessmentDetailOut,
             status_code=status.HTTP_201_CREATED)
def generate_assessment(
    system_id: int,
    body: AssessmentGenerateIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    """Створює оцінювання з контролів профілю (результат — not_assessed на кожен)."""
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

    assessment = Assessment(
        system_id=system.id,
        profile_id=profile.id,
        title=body.title or f"Оцінювання — {system.name}",
        status=AssessmentStatus.IN_PROGRESS.value,
        assessor_id=actor.id,
    )
    db.add(assessment)
    db.flush()
    for pc in profile.controls:
        if pc.included:
            db.add(AssessmentResult(
                assessment_id=assessment.id, requirement_id=pc.requirement_id
            ))
    log_action(db, actor, "create", "assessment", assessment.id, {"system": system.code})
    db.commit()
    return _detail(db, assessment.id)


@router.get("/systems/{system_id}/assessments", response_model=list[AssessmentOut])
def list_assessments(
    system_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    items = db.scalars(
        select(Assessment).where(Assessment.system_id == system_id)
        .options(selectinload(Assessment.results), selectinload(Assessment.assessor))
        .order_by(Assessment.id)
    ).all()
    return [_out(a) for a in items]


@router.get("/assessments/{assessment_id}", response_model=AssessmentDetailOut)
def get_assessment(
    assessment_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    detail = _detail(db, assessment_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Оцінювання не знайдено")
    return detail


@router.patch("/assessments/{assessment_id}", response_model=AssessmentOut)
def update_assessment(
    assessment_id: int,
    body: AssessmentUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    a = db.get(Assessment, assessment_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Оцінювання не знайдено")
    if body.title is not None:
        a.title = body.title
    if body.status is not None:
        a.status = body.status
        a.completed_at = (
            datetime.now(timezone.utc) if body.status == AssessmentStatus.COMPLETED.value else None
        )
    db.commit()
    a = db.scalar(select(Assessment).where(Assessment.id == assessment_id)
                  .options(selectinload(Assessment.results), selectinload(Assessment.assessor)))
    return _out(a)


@router.put("/assessments/{assessment_id}/results/{requirement_id}",
            response_model=AssessmentDetailOut)
def set_result(
    assessment_id: int,
    requirement_id: int,
    body: AssessmentResultIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    a = db.get(Assessment, assessment_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Оцінювання не знайдено")
    result = db.scalar(
        select(AssessmentResult).where(
            AssessmentResult.assessment_id == assessment_id,
            AssessmentResult.requirement_id == requirement_id,
        )
    )
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Контроль не в оцінюванні")
    result.result = body.result
    result.notes = body.notes
    result.assessed_at = datetime.now(timezone.utc)
    result.assessed_by_id = actor.id
    db.commit()
    return _detail(db, assessment_id)


@router.post("/assessments/{assessment_id}/to-poam", response_model=POAMFromProfileOut)
def assessment_to_poam(
    assessment_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    """Створює пункти POA&M для контролів з результатом other-than-satisfied
    (уникає дублів за відкритими пунктами)."""
    a = db.scalar(
        select(Assessment).where(Assessment.id == assessment_id)
        .options(selectinload(Assessment.results).selectinload(AssessmentResult.requirement))
    )
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Оцінювання не знайдено")

    open_reqs = set(db.scalars(
        select(POAMItem.requirement_id).where(
            POAMItem.system_id == a.system_id,
            POAMItem.status != POAMStatus.COMPLETED.value,
            POAMItem.requirement_id.isnot(None),
        )
    ).all())

    created, skipped = [], 0
    for r in a.results:
        if r.result != AssessmentResultValue.OTHER_THAN_SATISFIED.value:
            continue
        if r.requirement_id in open_reqs:
            skipped += 1
            continue
        item = POAMItem(
            system_id=a.system_id,
            requirement_id=r.requirement_id,
            title=f"Не задоволено: {r.requirement.code} {r.requirement.title}",
            weakness=r.notes or "Контроль оцінено як other-than-satisfied.",
            status=POAMStatus.OPEN.value,
            source=POAMSource.FROM_FINDING.value,
        )
        db.add(item)
        open_reqs.add(r.requirement_id)
        created.append(item)
    db.flush()
    log_action(db, actor, "to_poam", "assessment", a.id, {"created": len(created)})
    db.commit()
    return POAMFromProfileOut(
        created=len(created), skipped=skipped,
        items=[_item_out(db.get(POAMItem, i.id)) for i in created],
    )
