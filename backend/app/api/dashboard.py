from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.frameworks import requirement_applies, requirement_coverage
from app.core.deps import get_current_user
from app.database import get_db
from app.models import (
    ActionStatus,
    ControlImplementation,
    InformationSystem,
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
def dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    system_id: int | None = None,
):
    today = date.today()
    risk_query = select(Risk).options(selectinload(Risk.category), selectinload(Risk.owner))
    if system_id:
        risk_query = risk_query.where(
            Risk.systems.any(InformationSystem.id == system_id) | ~Risk.systems.any()
        )
    risks = db.scalars(risk_query).all()
    profile_type = None
    if system_id:
        system = db.get(InformationSystem, system_id)
        profile_type = system.profile_type if system else None

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

    impl_query = select(ControlImplementation.id).where(
        ControlImplementation.next_review_date < today
    )
    if system_id:
        impl_query = impl_query.where(
            (ControlImplementation.system_id == system_id)
            | ControlImplementation.system_id.is_(None)
        )
    overdue_control_reviews = len(db.scalars(impl_query).all())
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
            .options(
                selectinload(Requirement.controls).selectinload(Control.implementations)
            )
        ).all()
        requirements = [r for r in requirements if requirement_applies(r, profile_type)]
        coverages = [requirement_coverage(r, system_id) for r in requirements]
        covered = sum(1 for c in coverages if c == "covered")
        na = sum(1 for c in coverages if c == "not_applicable")
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
