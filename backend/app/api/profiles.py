"""Цільові профілі ІКС + tailoring (RMF «Select», ТЗ §5).

Генерація профілю з baseline, адаптація (tailoring) з обов'язковим обґрунтуванням,
версіонування, затвердження, резолвлене подання та overlays.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user, require_admin
from app.database import get_db
from app.models import (
    Baseline,
    BaselineItem,
    ControlOrigin,
    ControlParameter,
    Framework,
    InformationSystem,
    Overlay,
    OverlayItem,
    Profile,
    ProfileControl,
    ProfileParameterValue,
    ProfileStatus,
    Requirement,
    TailoringAction,
    TailoringDecision,
    User,
)
from app.schemas import (
    ApplyOverlayIn,
    OverlayDetailOut,
    OverlayIn,
    OverlayItemOut,
    OverlayOut,
    ProfileControlOut,
    ProfileDetailOut,
    ProfileGenerateIn,
    ProfileOut,
    ResolvedControlOut,
    ResolvedParameterOut,
    ResolvedProfileOut,
    TailoringDecisionOut,
    TailoringIn,
)
from app.services.audit import log_action

router = APIRouter(tags=["profiles"])

_PROFILE_LOAD = [
    selectinload(Profile.controls).selectinload(ProfileControl.requirement),
    selectinload(Profile.decisions).selectinload(TailoringDecision.created_by),
    selectinload(Profile.parameter_values),
]


def _profile_out(profile: Profile) -> ProfileOut:
    out = ProfileOut.model_validate(profile)
    out.control_count = sum(1 for c in profile.controls if c.included)
    return out


def _detail(db: Session, profile_id: int) -> ProfileDetailOut | None:
    profile = db.scalar(
        select(Profile).where(Profile.id == profile_id).options(*_PROFILE_LOAD)
    )
    if profile is None:
        return None
    base = _profile_out(profile)
    return ProfileDetailOut(
        **base.model_dump(),
        controls=[ProfileControlOut.model_validate(c) for c in profile.controls],
        decisions=[TailoringDecisionOut.model_validate(d) for d in profile.decisions],
    )


def _get_draft(db: Session, profile_id: int) -> Profile:
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Профіль не знайдено")
    if profile.status != ProfileStatus.DRAFT.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Профіль не в статусі чернетки — створіть нову версію для змін",
        )
    return profile


# --- Генерація / перегляд ---

@router.post(
    "/systems/{system_id}/profiles",
    response_model=ProfileDetailOut,
    status_code=status.HTTP_201_CREATED,
)
def generate_profile(
    system_id: int,
    body: ProfileGenerateIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    """Генерує цільовий профіль ІКС із baseline: ProfileControl на кожен BaselineItem."""
    system = db.get(InformationSystem, system_id)
    if system is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Систему не знайдено")
    baseline = db.get(Baseline, body.baseline_id)
    if baseline is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Baseline не знайдено")

    profile = Profile(
        system_id=system.id,
        baseline_id=baseline.id,
        name=body.name or f"{system.code} — {baseline.name}",
        version=1,
        status=ProfileStatus.DRAFT.value,
    )
    db.add(profile)
    db.flush()

    requirement_ids = db.scalars(
        select(BaselineItem.requirement_id).where(BaselineItem.baseline_id == baseline.id)
    ).all()
    for rid in requirement_ids:
        db.add(
            ProfileControl(
                profile_id=profile.id,
                requirement_id=rid,
                included=True,
                origin=ControlOrigin.BASELINE.value,
            )
        )
    log_action(
        db, actor, "create", "profile", profile.id,
        {"system": system.code, "baseline_id": baseline.id, "controls": len(requirement_ids)},
    )
    db.commit()
    return _detail(db, profile.id)


@router.get("/systems/{system_id}/profiles", response_model=list[ProfileOut])
def list_profiles(
    system_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    profiles = db.scalars(
        select(Profile)
        .where(Profile.system_id == system_id)
        .options(selectinload(Profile.controls))
        .order_by(Profile.id)
    ).all()
    return [_profile_out(p) for p in profiles]


@router.get("/profiles/{profile_id}", response_model=ProfileDetailOut)
def get_profile(
    profile_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    detail = _detail(db, profile_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Профіль не знайдено")
    return detail


# --- Tailoring ---

@router.post("/profiles/{profile_id}/tailoring", response_model=ProfileDetailOut)
def tailor_profile(
    profile_id: int,
    body: TailoringIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    """Рішення tailoring (add/remove/modify_param) з обов'язковим обґрунтуванням."""
    profile = _get_draft(db, profile_id)
    requirement_id = body.requirement_id

    if body.action == TailoringAction.REMOVE:
        if requirement_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Вкажіть requirement_id")
        pc = db.scalar(
            select(ProfileControl).where(
                ProfileControl.profile_id == profile.id,
                ProfileControl.requirement_id == requirement_id,
            )
        )
        if pc is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Контроль не в профілі")
        pc.included = False

    elif body.action == TailoringAction.ADD:
        if requirement_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Вкажіть requirement_id")
        requirement = db.get(Requirement, requirement_id)
        if requirement is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Вимогу не знайдено")
        if profile.baseline_id:
            baseline = db.get(Baseline, profile.baseline_id)
            if baseline and requirement.framework_id != baseline.catalog_id:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "Контроль належить іншому каталогу, ніж baseline профілю",
                )
        pc = db.scalar(
            select(ProfileControl).where(
                ProfileControl.profile_id == profile.id,
                ProfileControl.requirement_id == requirement_id,
            )
        )
        if pc is not None:
            if pc.included:
                raise HTTPException(status.HTTP_409_CONFLICT, "Контроль уже в профілі")
            pc.included = True  # повторне включення раніше вилученого
        else:
            db.add(
                ProfileControl(
                    profile_id=profile.id,
                    requirement_id=requirement_id,
                    included=True,
                    origin=ControlOrigin.ADDED.value,
                )
            )

    elif body.action == TailoringAction.MODIFY_PARAM:
        if body.parameter_id is None or body.value is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Вкажіть parameter_id і value"
            )
        param = db.get(ControlParameter, body.parameter_id)
        if param is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Параметр не знайдено")
        requirement_id = param.requirement_id
        existing = db.scalar(
            select(ProfileParameterValue).where(
                ProfileParameterValue.profile_id == profile.id,
                ProfileParameterValue.parameter_id == param.id,
            )
        )
        if existing:
            existing.value = body.value
        else:
            db.add(
                ProfileParameterValue(
                    profile_id=profile.id, parameter_id=param.id, value=body.value
                )
            )

    db.add(
        TailoringDecision(
            profile_id=profile.id,
            requirement_id=requirement_id,
            action=body.action.value,
            justification=body.justification,
            parameter_id=body.parameter_id,
            value=body.value,
            created_by_id=actor.id,
        )
    )
    log_action(
        db, actor, "tailor", "profile", profile.id,
        {"action": body.action.value, "requirement_id": requirement_id},
    )
    db.commit()
    return _detail(db, profile.id)


# --- Затвердження / версіонування ---

@router.post("/profiles/{profile_id}/approve", response_model=ProfileOut)
def approve_profile(
    profile_id: int, db: Session = Depends(get_db), actor: User = Depends(require_admin)
):
    profile = _get_draft(db, profile_id)
    profile.status = ProfileStatus.APPROVED.value
    profile.approved_at = datetime.now(timezone.utc)
    profile.approved_by_id = actor.id
    log_action(db, actor, "approve", "profile", profile.id, {"version": profile.version})
    db.commit()
    db.refresh(profile)
    return _profile_out_loaded(db, profile.id)


def _profile_out_loaded(db: Session, profile_id: int) -> ProfileOut:
    profile = db.scalar(
        select(Profile).where(Profile.id == profile_id).options(selectinload(Profile.controls))
    )
    return _profile_out(profile)


@router.post(
    "/profiles/{profile_id}/new-version",
    response_model=ProfileDetailOut,
    status_code=status.HTTP_201_CREATED,
)
def new_version(
    profile_id: int, db: Session = Depends(get_db), actor: User = Depends(require_admin)
):
    """Створює нову чернетку-версію з копією контролів і параметрів; стару позначає superseded."""
    src = db.scalar(
        select(Profile).where(Profile.id == profile_id).options(*_PROFILE_LOAD)
    )
    if src is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Профіль не знайдено")

    new = Profile(
        system_id=src.system_id,
        baseline_id=src.baseline_id,
        parent_profile_id=src.id,
        name=src.name,
        version=src.version + 1,
        status=ProfileStatus.DRAFT.value,
    )
    db.add(new)
    db.flush()
    for pc in src.controls:
        db.add(
            ProfileControl(
                profile_id=new.id,
                requirement_id=pc.requirement_id,
                included=pc.included,
                origin=pc.origin,
            )
        )
    for pv in src.parameter_values:
        db.add(
            ProfileParameterValue(
                profile_id=new.id, parameter_id=pv.parameter_id, value=pv.value
            )
        )
    src.status = ProfileStatus.SUPERSEDED.value
    log_action(
        db, actor, "new_version", "profile", new.id,
        {"from": src.id, "version": new.version},
    )
    db.commit()
    return _detail(db, new.id)


# --- Резолвлене подання (для SSP/звітів) ---

@router.get("/profiles/{profile_id}/resolved", response_model=ResolvedProfileOut)
def resolved_profile(
    profile_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    """Підсумковий набір контролів профілю: лише включені, з резолвленими ODP-значеннями
    (значення профілю або default) і текстом вимоги під тип профілю ІКС."""
    profile = db.scalar(
        select(Profile)
        .where(Profile.id == profile_id)
        .options(
            selectinload(Profile.controls)
            .selectinload(ProfileControl.requirement)
            .selectinload(Requirement.parameters),
            selectinload(Profile.parameter_values),
        )
    )
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Профіль не знайдено")

    system = db.get(InformationSystem, profile.system_id)
    profile_type = system.profile_type if system else None
    pv_map = {pv.parameter_id: pv.value for pv in profile.parameter_values}

    controls: list[ResolvedControlOut] = []
    for pc in profile.controls:
        if not pc.included:
            continue
        req = pc.requirement
        description = req.description
        if profile_type and req.profile_descriptions:
            specific = req.profile_descriptions.get(profile_type)
            if specific:
                description = specific
        controls.append(
            ResolvedControlOut(
                requirement_id=req.id,
                code=req.code,
                title=req.title,
                description=description,
                origin=pc.origin,
                parameters=[
                    ResolvedParameterOut(
                        parameter_id=p.id,
                        key=p.key,
                        label=p.label,
                        value=pv_map.get(p.id, p.default_value),
                    )
                    for p in req.parameters
                ],
            )
        )
    return ResolvedProfileOut(
        profile_id=profile.id,
        system_id=profile.system_id,
        name=profile.name,
        version=profile.version,
        status=profile.status,
        control_count=len(controls),
        controls=controls,
    )


# --- Overlays ---

def _overlay_out(overlay: Overlay) -> OverlayOut:
    out = OverlayOut.model_validate(overlay)
    out.item_count = len(overlay.items)
    return out


@router.get("/overlays", response_model=list[OverlayOut])
def list_overlays(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    overlays = db.scalars(
        select(Overlay).options(selectinload(Overlay.items)).order_by(Overlay.id)
    ).all()
    return [_overlay_out(o) for o in overlays]


@router.post("/overlays", response_model=OverlayDetailOut, status_code=status.HTTP_201_CREATED)
def create_overlay(
    body: OverlayIn, db: Session = Depends(get_db), actor: User = Depends(require_admin)
):
    if db.get(Framework, body.catalog_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Каталог не знайдено")
    overlay = Overlay(catalog_id=body.catalog_id, name=body.name, description=body.description)
    db.add(overlay)
    db.flush()
    for item in body.items:
        db.add(
            OverlayItem(
                overlay_id=overlay.id,
                requirement_id=item.requirement_id,
                action=item.action,
            )
        )
    log_action(db, actor, "create", "overlay", overlay.id, {"name": overlay.name})
    db.commit()
    return _overlay_detail(db, overlay.id)


@router.get("/overlays/{overlay_id}", response_model=OverlayDetailOut)
def get_overlay(
    overlay_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    detail = _overlay_detail(db, overlay_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Overlay не знайдено")
    return detail


def _overlay_detail(db: Session, overlay_id: int) -> OverlayDetailOut | None:
    overlay = db.scalar(
        select(Overlay).where(Overlay.id == overlay_id).options(selectinload(Overlay.items))
    )
    if overlay is None:
        return None
    out = _overlay_out(overlay)
    return OverlayDetailOut(
        **out.model_dump(),
        items=[OverlayItemOut.model_validate(i) for i in overlay.items],
    )


@router.post(
    "/profiles/{profile_id}/apply-overlay/{overlay_id}", response_model=ProfileDetailOut
)
def apply_overlay(
    profile_id: int,
    overlay_id: int,
    body: ApplyOverlayIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    """Застосовує overlay до чернетки профілю — кожен пункт фіксується як TailoringDecision."""
    profile = _get_draft(db, profile_id)
    overlay = db.scalar(
        select(Overlay).where(Overlay.id == overlay_id).options(selectinload(Overlay.items))
    )
    if overlay is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Overlay не знайдено")

    justification = f"Overlay «{overlay.name}»: {body.justification}"
    for item in overlay.items:
        pc = db.scalar(
            select(ProfileControl).where(
                ProfileControl.profile_id == profile.id,
                ProfileControl.requirement_id == item.requirement_id,
            )
        )
        if item.action == "add":
            if pc is not None:
                pc.included = True
            else:
                db.add(
                    ProfileControl(
                        profile_id=profile.id,
                        requirement_id=item.requirement_id,
                        included=True,
                        origin=ControlOrigin.ADDED.value,
                    )
                )
        elif item.action == "remove" and pc is not None:
            pc.included = False
        db.add(
            TailoringDecision(
                profile_id=profile.id,
                requirement_id=item.requirement_id,
                action=(TailoringAction.ADD.value if item.action == "add"
                        else TailoringAction.REMOVE.value),
                justification=justification,
                created_by_id=actor.id,
            )
        )
    log_action(
        db, actor, "apply_overlay", "profile", profile.id,
        {"overlay_id": overlay.id, "items": len(overlay.items)},
    )
    db.commit()
    return _detail(db, profile.id)
