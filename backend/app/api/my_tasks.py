from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user
from app.database import get_db
from app.models import (
    ActionStatus,
    ApprovalDecision,
    Control,
    ControlImplementation,
    Finding,
    Policy,
    PolicyAck,
    PolicyApproval,
    PolicyStatus,
    PolicyVersion,
    Risk,
    RiskStatus,
    TreatmentAction,
    User,
)
from app.schemas_phase4 import MyTask

router = APIRouter(prefix="/my-tasks", tags=["my-tasks"])

_OPEN_ACTION = [ActionStatus.OPEN.value, ActionStatus.IN_PROGRESS.value]
_OPEN_RISK = [s.value for s in RiskStatus if s != RiskStatus.CLOSED]


@router.get("", response_model=list[MyTask])
def my_tasks(db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    today = date.today()
    tasks: list[MyTask] = []

    def add(kind, title, entity_type, entity_id, entity_code, due=None):
        tasks.append(MyTask(
            kind=kind, title=title, entity_type=entity_type, entity_id=entity_id,
            entity_code=entity_code, due_date=due,
            overdue=bool(due and due < today),
        ))

    for action in db.scalars(
        select(TreatmentAction)
        .where(TreatmentAction.assignee_id == actor.id, TreatmentAction.status.in_(_OPEN_ACTION))
        .options(selectinload(TreatmentAction.risk))
    ):
        add("treatment_action", action.title, "risk", action.risk_id,
            action.risk.code, action.deadline)

    for finding in db.scalars(
        select(Finding)
        .where(Finding.responsible_id == actor.id, Finding.action_status.in_(_OPEN_ACTION))
        .options(selectinload(Finding.audit))
    ):
        add("finding", f"{finding.code}: {finding.action_title or finding.title}",
            "audit", finding.audit_id, finding.audit.code, finding.deadline)

    for approval in db.scalars(
        select(PolicyApproval)
        .where(
            PolicyApproval.approver_id == actor.id,
            PolicyApproval.decision == ApprovalDecision.PENDING.value,
        )
        .options(selectinload(PolicyApproval.version).selectinload(PolicyVersion.policy))
    ):
        policy = approval.version.policy
        if policy.status == PolicyStatus.APPROVAL.value:
            add("approval", f"Погодити: {policy.title}", "policy", policy.id, policy.code)

    for ack in db.scalars(
        select(PolicyAck)
        .where(PolicyAck.user_id == actor.id, PolicyAck.acknowledged_at.is_(None))
        .options(selectinload(PolicyAck.version).selectinload(PolicyVersion.policy))
    ):
        policy = ack.version.policy
        add("ack", f"Ознайомитись: {policy.title}", "policy", policy.id, policy.code)

    for risk in db.scalars(
        select(Risk).where(
            Risk.owner_id == actor.id,
            Risk.next_review_date < today,
            Risk.status.in_(_OPEN_RISK),
        )
    ):
        add("risk_review", f"Переглянути ризик: {risk.title}", "risk", risk.id,
            risk.code, risk.next_review_date)

    for impl in db.scalars(
        select(ControlImplementation)
        .join(Control)
        .where(Control.owner_id == actor.id, ControlImplementation.next_review_date < today)
        .options(
            selectinload(ControlImplementation.control),
            selectinload(ControlImplementation.system),
        )
    ):
        suffix = f" ({impl.system.name})" if impl.system else ""
        add("control_review", f"Перевірити контроль: {impl.control.name}{suffix}",
            "control", impl.control_id, impl.control.code, impl.next_review_date)

    for policy in db.scalars(
        select(Policy).where(
            Policy.owner_id == actor.id,
            Policy.next_review_date < today,
            Policy.status == PolicyStatus.ACTIVE.value,
        )
    ):
        add("policy_review", f"Переглянути політику: {policy.title}", "policy",
            policy.id, policy.code, policy.next_review_date)

    tasks.sort(key=lambda t: (not t.overdue, t.due_date or date.max))
    return tasks
