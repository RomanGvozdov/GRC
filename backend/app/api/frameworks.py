from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user
from app.database import get_db
from app.models import Framework, ImplementationStatus, Requirement, User
from app.schemas import FrameworkOut, GapRequirement, GapSummary, RequirementOut

router = APIRouter(prefix="/frameworks", tags=["compliance"])


@router.get("", response_model=list[FrameworkOut])
def list_frameworks(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.scalars(select(Framework).order_by(Framework.id)).all()


@router.get("/{framework_id}/requirements", response_model=list[RequirementOut])
def list_requirements(
    framework_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    if db.get(Framework, framework_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Фреймворк не знайдено")
    return db.scalars(
        select(Requirement).where(Requirement.framework_id == framework_id).order_by(Requirement.id)
    ).all()


def requirement_coverage(requirement: Requirement) -> str:
    """Покриття вимоги контролями: covered / partial / not_covered / not_applicable."""
    controls = requirement.controls
    if not controls:
        return "not_covered"
    statuses = {c.implementation_status for c in controls}
    if statuses == {ImplementationStatus.NOT_APPLICABLE.value}:
        return "not_applicable"
    if ImplementationStatus.IMPLEMENTED.value in statuses:
        return "covered"
    if ImplementationStatus.PARTIAL.value in statuses:
        return "partial"
    return "not_covered"


@router.get("/{framework_id}/gap-analysis", response_model=GapSummary)
def gap_analysis(
    framework_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    framework = db.get(Framework, framework_id)
    if framework is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Фреймворк не знайдено")

    requirements = db.scalars(
        select(Requirement)
        .where(Requirement.framework_id == framework_id)
        .options(selectinload(Requirement.controls))
        .order_by(Requirement.id)
    ).all()

    items: list[GapRequirement] = []
    counts = {"covered": 0, "partial": 0, "not_covered": 0, "not_applicable": 0}
    for requirement in requirements:
        coverage = requirement_coverage(requirement)
        counts[coverage] += 1
        items.append(
            GapRequirement(
                requirement=RequirementOut.model_validate(requirement),
                controls=requirement.controls,
                coverage=coverage,
            )
        )

    applicable = len(requirements) - counts["not_applicable"]
    percent = round(counts["covered"] / applicable * 100, 1) if applicable else 0.0
    return GapSummary(
        framework=FrameworkOut.model_validate(framework),
        total=len(requirements),
        covered=counts["covered"],
        partial=counts["partial"],
        not_covered=counts["not_covered"],
        not_applicable=counts["not_applicable"],
        coverage_percent=percent,
        requirements=items,
    )
