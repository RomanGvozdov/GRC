from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.core.deps import can_edit_entity, get_current_user, require_permission

require_risk_manager = require_permission("risks", "manage")
require_risk_reader = require_permission("risks", "read")
from app.database import get_db
from app.models import (
    Control,
    InformationSystem,
    Risk,
    RiskAssessment,
    RiskStatus,
    TreatmentAction,
    TreatmentStrategy,
    User,
    risk_level,
)
from app.schemas import (
    AssessmentIn,
    RiskBrief,
    RiskIn,
    RiskOut,
    TreatmentActionIn,
    TreatmentActionOut,
)
from app.services.audit import log_action
from app.services.notify import notify_user

router = APIRouter(prefix="/risks", tags=["risks"])


def next_code(db: Session) -> str:
    last_id = db.scalar(select(Risk.id).order_by(Risk.id.desc()).limit(1)) or 0
    return f"RISK-{last_id + 1:03d}"


def _get_risk(db: Session, risk_id: int) -> Risk:
    risk = db.get(
        Risk,
        risk_id,
        options=[
            selectinload(Risk.controls),
            selectinload(Risk.assessments),
            selectinload(Risk.actions),
        ],
    )
    if risk is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ризик не знайдено")
    return risk


def _check_edit(user: User, risk: Risk) -> None:
    if not can_edit_entity(user, risk.owner_id, "risks"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ви не є відповідальним за цей ризик")


def _check_acceptance(user: User, risk: Risk, body: RiskIn) -> None:
    """Прийняття ризику вище порога вимагає ролі менеджера та коментаря."""
    if body.treatment_strategy != TreatmentStrategy.ACCEPT:
        return
    score = risk_level(risk.residual_likelihood, risk.residual_impact)
    if score is None or score < get_settings().risk_acceptance_threshold:
        return
    from app.models import Role

    if user.role not in (Role.ADMIN.value, Role.GRC_MANAGER.value):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Прийняття ризику високого рівня може затвердити лише GRC-менеджер",
        )
    if not body.acceptance_comment:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Прийняття ризику високого рівня вимагає коментаря-обґрунтування",
        )
    risk.accepted_by_id = user.id
    risk.accepted_at = datetime.now(timezone.utc)


@router.get("", response_model=list[RiskBrief])
def list_risks(
    db: Session = Depends(get_db),
    _: User = Depends(require_risk_reader),
    status_filter: RiskStatus | None = Query(default=None, alias="status"),
    category_id: int | None = None,
    owner_id: int | None = None,
    system_id: int | None = None,
    level: str | None = Query(default=None, pattern="^(low|medium|high|critical)$"),
    search: str | None = None,
):
    query = select(Risk).options(
        selectinload(Risk.category), selectinload(Risk.owner), selectinload(Risk.systems)
    )
    if system_id:
        query = query.where(Risk.systems.any(InformationSystem.id == system_id) | ~Risk.systems.any())
    if status_filter:
        query = query.where(Risk.status == status_filter.value)
    if category_id:
        query = query.where(Risk.category_id == category_id)
    if owner_id:
        query = query.where(Risk.owner_id == owner_id)
    if search:
        pattern = f"%{search}%"
        query = query.where(Risk.title.ilike(pattern) | Risk.code.ilike(pattern))
    risks = db.scalars(query.order_by(Risk.id.desc())).all()
    if level:
        bounds = {"low": (1, 4), "medium": (5, 9), "high": (10, 14), "critical": (15, 25)}[level]
        risks = [
            r
            for r in risks
            if (s := risk_level(r.residual_likelihood, r.residual_impact)) is not None
            and bounds[0] <= s <= bounds[1]
        ]
    return risks


@router.post("", response_model=RiskOut, status_code=status.HTTP_201_CREATED)
def create_risk(
    body: RiskIn, db: Session = Depends(get_db), actor: User = Depends(require_risk_manager)
):
    risk = Risk(
        code=next_code(db),
        **body.model_dump(exclude={"treatment_strategy", "system_ids"}),
    )
    risk.systems = list(
        db.scalars(
            select(InformationSystem).where(InformationSystem.id.in_(body.system_ids))
        ).all()
    )
    risk.status = body.status.value
    risk.treatment_strategy = (
        body.treatment_strategy.value if body.treatment_strategy else None
    )
    db.add(risk)
    db.flush()
    log_action(db, actor, "create", "risk", risk.id, {"code": risk.code, "title": risk.title})
    db.commit()
    if risk.owner_id and risk.owner_id != actor.id:
        notify_user(
            db.get(User, risk.owner_id),
            f"GRC: вам призначено ризик {risk.code}",
            f"Вас призначено відповідальним за ризик {risk.code} — {risk.title}.",
        )
    return _get_risk(db, risk.id)


@router.get("/{risk_id}", response_model=RiskOut)
def get_risk(risk_id: int, db: Session = Depends(get_db), _: User = Depends(require_risk_reader)):
    return _get_risk(db, risk_id)


@router.put("/{risk_id}", response_model=RiskOut)
def update_risk(
    risk_id: int,
    body: RiskIn,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    risk = _get_risk(db, risk_id)
    _check_edit(actor, risk)
    _check_acceptance(actor, risk, body)
    previous_owner_id = risk.owner_id

    data = body.model_dump(exclude={"system_ids"})
    data["status"] = body.status.value
    risk.systems = list(
        db.scalars(
            select(InformationSystem).where(InformationSystem.id.in_(body.system_ids))
        ).all()
    )
    data["treatment_strategy"] = (
        body.treatment_strategy.value if body.treatment_strategy else None
    )
    for field, value in data.items():
        setattr(risk, field, value)
    log_action(db, actor, "update", "risk", risk.id, {"code": risk.code})
    db.commit()
    if risk.owner_id and risk.owner_id not in (previous_owner_id, actor.id):
        notify_user(
            db.get(User, risk.owner_id),
            f"GRC: вам призначено ризик {risk.code}",
            f"Вас призначено відповідальним за ризик {risk.code} — {risk.title}.",
        )
    return _get_risk(db, risk_id)


@router.delete("/{risk_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_risk(
    risk_id: int, db: Session = Depends(get_db), actor: User = Depends(require_risk_manager)
):
    risk = _get_risk(db, risk_id)
    log_action(db, actor, "delete", "risk", risk.id, {"code": risk.code, "title": risk.title})
    db.delete(risk)
    db.commit()


@router.post("/{risk_id}/assessments", response_model=RiskOut)
def add_assessment(
    risk_id: int,
    body: AssessmentIn,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    risk = _get_risk(db, risk_id)
    _check_edit(actor, risk)

    risk.assessments.append(
        RiskAssessment(
            kind=body.kind,
            likelihood=body.likelihood,
            impact=body.impact,
            assessed_by_id=actor.id,
        )
    )
    if body.kind == "inherent":
        risk.inherent_likelihood, risk.inherent_impact = body.likelihood, body.impact
    else:
        risk.residual_likelihood, risk.residual_impact = body.likelihood, body.impact
    if risk.status in (RiskStatus.DRAFT.value, RiskStatus.IDENTIFIED.value):
        risk.status = RiskStatus.ASSESSED.value
    log_action(
        db, actor, "assess", "risk", risk.id,
        {"kind": body.kind, "likelihood": body.likelihood, "impact": body.impact},
    )
    db.commit()
    return _get_risk(db, risk_id)


@router.post("/{risk_id}/actions", response_model=TreatmentActionOut, status_code=201)
def add_action(
    risk_id: int,
    body: TreatmentActionIn,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    risk = _get_risk(db, risk_id)
    _check_edit(actor, risk)
    action = TreatmentAction(
        risk_id=risk.id,
        title=body.title,
        assignee_id=body.assignee_id,
        deadline=body.deadline,
        status=body.status.value,
    )
    db.add(action)
    db.flush()
    log_action(db, actor, "create", "treatment_action", action.id, {"risk": risk.code})
    db.commit()
    if action.assignee_id and action.assignee_id != actor.id:
        notify_user(
            db.get(User, action.assignee_id),
            f"GRC: нова дія за ризиком {risk.code}",
            f"Вам призначено дію «{action.title}» за ризиком {risk.code} — {risk.title}"
            + (f" (дедлайн {action.deadline:%d.%m.%Y})." if action.deadline else "."),
        )
    return db.get(TreatmentAction, action.id)


@router.patch("/{risk_id}/actions/{action_id}", response_model=TreatmentActionOut)
def update_action(
    risk_id: int,
    action_id: int,
    body: TreatmentActionIn,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    risk = _get_risk(db, risk_id)
    action = db.get(TreatmentAction, action_id)
    if action is None or action.risk_id != risk.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Дію не знайдено")
    # Виконавець може оновлювати дію, якщо відповідає за ризик або призначений на дію
    if not (
        can_edit_entity(actor, risk.owner_id, "risks")
        or can_edit_entity(actor, action.assignee_id, "risks")
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ви не призначені на цю дію")
    action.title = body.title
    action.assignee_id = body.assignee_id
    action.deadline = body.deadline
    action.status = body.status.value
    log_action(db, actor, "update", "treatment_action", action.id, {"status": body.status.value})
    db.commit()
    return action


@router.delete("/{risk_id}/actions/{action_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_action(
    risk_id: int,
    action_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_risk_manager),
):
    action = db.get(TreatmentAction, action_id)
    if action is None or action.risk_id != risk_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Дію не знайдено")
    log_action(db, actor, "delete", "treatment_action", action.id)
    db.delete(action)
    db.commit()


@router.put("/{risk_id}/controls", response_model=RiskOut)
def set_controls(
    risk_id: int,
    control_ids: list[int],
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    risk = _get_risk(db, risk_id)
    _check_edit(actor, risk)
    controls = db.scalars(select(Control).where(Control.id.in_(control_ids))).all()
    if len(controls) != len(set(control_ids)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Деякі контролі не знайдено")
    risk.controls = list(controls)
    log_action(db, actor, "link_controls", "risk", risk.id, {"control_ids": control_ids})
    db.commit()
    return _get_risk(db, risk_id)
