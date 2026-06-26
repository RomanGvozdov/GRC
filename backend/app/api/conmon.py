"""Безперервний моніторинг (ConMon, ТЗ §7): авто-докази + дашборд здоров'я.

`POST /api/ingest/evidence` приймає докази від сканерів/CIS за API-токеном
(`controls:write`) і прив'язує їх до ІКС+контролю. Здоров'я рахується за контролями
поточного профілю ІКС: свіжі / прострочені (дрейф) / без доказів.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user, require_permission
from app.database import get_db
from app.models import (
    Baseline,
    Evidence,
    InformationSystem,
    Profile,
    ProfileControl,
    Requirement,
    User,
)
from app.schemas import ConMonControlOut, ConMonHealthOut, EvidenceIngestIn, EvidenceOut
from app.services.audit import log_action

router = APIRouter(tags=["conmon"])

require_ingest = require_permission("controls", "write")


def _resolve_requirement(db: Session, system_id: int, code: str) -> Requirement | None:
    """Знаходить вимогу за кодом, віддаючи перевагу каталогу профілю ІКС."""
    profile = db.scalar(
        select(Profile).where(Profile.system_id == system_id).order_by(Profile.id.desc()).limit(1)
    )
    if profile and profile.baseline_id:
        baseline = db.get(Baseline, profile.baseline_id)
        if baseline:
            req = db.scalar(
                select(Requirement).where(
                    Requirement.framework_id == baseline.catalog_id, Requirement.code == code
                )
            )
            if req:
                return req
    return db.scalar(select(Requirement).where(Requirement.code == code).limit(1))


@router.post("/ingest/evidence", response_model=EvidenceOut,
             status_code=status.HTTP_201_CREATED)
def ingest_evidence(
    body: EvidenceIngestIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_ingest),
):
    """Авто-доказ від сканера/CIS (за API-токеном). Прив'язується до ІКС+контролю."""
    if db.get(InformationSystem, body.system_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Систему не знайдено")
    req = _resolve_requirement(db, body.system_id, body.requirement_code)
    if req is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Контроль «{body.requirement_code}» не знайдено"
        )
    evidence = Evidence(
        system_id=body.system_id,
        requirement_id=req.id,
        kind="link",
        name=body.name,
        url=body.url,
        valid_until=body.valid_until,
        source=body.source,
        automated=True,
        uploaded_by_id=actor.id,
    )
    db.add(evidence)
    db.flush()
    log_action(
        db, actor, "ingest", "evidence", evidence.id,
        {"system_id": body.system_id, "control": req.code, "source": body.source},
    )
    db.commit()
    return db.get(Evidence, evidence.id)


@router.get("/systems/{system_id}/conmon/health", response_model=ConMonHealthOut)
def conmon_health(
    system_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    """Здоров'я контролів ІКС за поточним профілем: свіжі/прострочені/без доказів."""
    if db.get(InformationSystem, system_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Систему не знайдено")
    profile = db.scalar(
        select(Profile).where(Profile.system_id == system_id)
        .options(selectinload(Profile.controls).selectinload(ProfileControl.requirement))
        .order_by(Profile.id.desc()).limit(1)
    )
    if profile is None:
        return ConMonHealthOut(system_id=system_id, profile_id=None,
                               total=0, fresh=0, stale=0, none=0, drift=[])

    req_by_id = {pc.requirement_id: pc.requirement for pc in profile.controls if pc.included}
    # Докази ІКС по цих контролях
    evidence = db.scalars(
        select(Evidence).where(
            Evidence.system_id == system_id,
            Evidence.requirement_id.in_(list(req_by_id) or [0]),
        )
    ).all()
    by_req: dict[int, list[Evidence]] = {}
    for e in evidence:
        by_req.setdefault(e.requirement_id, []).append(e)

    today = date.today()
    fresh = stale = none = 0
    drift: list[ConMonControlOut] = []
    for rid, req in req_by_id.items():
        evs = by_req.get(rid, [])
        if not evs:
            none += 1
            continue
        is_fresh = any(e.valid_until is None or e.valid_until >= today for e in evs)
        latest = max((e.valid_until for e in evs if e.valid_until), default=None)
        if is_fresh:
            fresh += 1
        else:
            stale += 1
            drift.append(ConMonControlOut(
                requirement_id=rid, code=req.code, title=req.title,
                state="stale", evidence_count=len(evs), latest_valid_until=latest,
            ))
    return ConMonHealthOut(
        system_id=system_id, profile_id=profile.id,
        total=len(req_by_id), fresh=fresh, stale=stale, none=none, drift=drift,
    )
