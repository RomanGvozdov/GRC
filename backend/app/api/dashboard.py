from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.frameworks import requirement_coverage
from app.core.deps import get_current_user
from app.database import get_db
from app.models import (
    ActionStatus,
    Policy,
    PolicyStatus,
    Control,
    Framework,
    Requirement,
    Risk,
    RiskStatus,
    TreatmentAction,
    User,
    risk_level,
    risk_level_label,
)
from app.schemas import DashboardOut, FrameworkCoverage, FrameworkOut, HeatMapCell

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_OPEN_STATUSES = [s.value for s in RiskStatus if s != RiskStatus.CLOSED]


@router.get("", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    today = date.today()
    risks = db.scalars(
        select(Risk).options(selectinload(Risk.category), selectinload(Risk.owner))
    ).all()

    by_status: dict[str, int] = {s.value: 0 for s in RiskStatus}
    by_level: dict[str, int] = {"low": 0, "medium": 0, "high": 0, "critical": 0, "unassessed": 0}
    heat: dict[tuple[int, int], int] = {}
    overdue_risk_reviews = 0
    scored: list[tuple[int, Risk]] = []

    for risk in risks:
        by_status[risk.status] = by_status.get(risk.status, 0) + 1
        is_open = risk.status in _OPEN_STATUSES
        score = risk_level(risk.residual_likelihood, risk.residual_impact)
        if is_open:
            if score is None:
                by_level["unassessed"] += 1
            else:
                by_level[risk_level_label(score)] += 1
                key = (risk.residual_likelihood, risk.residual_impact)
                heat[key] = heat.get(key, 0) + 1
                scored.append((score, risk))
            if risk.next_review_date and risk.next_review_date < today:
                overdue_risk_reviews += 1

    scored.sort(key=lambda pair: pair[0], reverse=True)
    top_risks = [risk for _, risk in scored[:5]]

    overdue_control_reviews = len(
        db.scalars(select(Control.id).where(Control.next_review_date < today)).all()
    )
    overdue_policy_reviews = len(
        db.scalars(
            select(Policy.id).where(
                Policy.next_review_date < today,
                Policy.status == PolicyStatus.ACTIVE.value,
            )
        ).all()
    )
    overdue_actions = len(
        db.scalars(
            select(TreatmentAction.id).where(
                TreatmentAction.deadline < today,
                TreatmentAction.status.in_(
                    [ActionStatus.OPEN.value, ActionStatus.IN_PROGRESS.value]
                ),
            )
        ).all()
    )

    frameworks_out: list[FrameworkCoverage] = []
    for framework in db.scalars(select(Framework).order_by(Framework.id)).all():
        requirements = db.scalars(
            select(Requirement)
            .where(Requirement.framework_id == framework.id)
            .options(selectinload(Requirement.controls))
        ).all()
        covered = sum(1 for r in requirements if requirement_coverage(r) == "covered")
        na = sum(1 for r in requirements if requirement_coverage(r) == "not_applicable")
        applicable = len(requirements) - na
        frameworks_out.append(
            FrameworkCoverage(
                framework=FrameworkOut.model_validate(framework),
                coverage_percent=round(covered / applicable * 100, 1) if applicable else 0.0,
                covered=covered,
                total=len(requirements),
            )
        )

    return DashboardOut(
        risks_total=len(risks),
        risks_by_status=by_status,
        risks_by_level=by_level,
        heat_map=[
            HeatMapCell(likelihood=k[0], impact=k[1], count=v) for k, v in sorted(heat.items())
        ],
        top_risks=top_risks,
        overdue_risk_reviews=overdue_risk_reviews,
        overdue_control_reviews=overdue_control_reviews,
        overdue_actions=overdue_actions,
        overdue_policy_reviews=overdue_policy_reviews,
        frameworks=frameworks_out,
    )
