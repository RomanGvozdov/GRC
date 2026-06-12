import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.core.deps import get_current_user, require_permission

require_policy_manager = require_permission("policies", "manage")
from app.database import get_db
from app.models import (
    ApprovalDecision,
    InformationSystem,
    Control,
    Policy,
    PolicyAck,
    PolicyApproval,
    PolicyStatus,
    PolicyVersion,
    User,
)
from app.schemas_phase2 import (
    AssignAcksIn,
    DecisionIn,
    PolicyContentIn,
    PolicyIn,
    PolicyListItem,
    PolicyOut,
    PolicyVersionOut,
    SubmitApprovalIn,
)
from app.services.audit import log_action
from app.services.notify import notify_user

router = APIRouter(prefix="/policies", tags=["policies"])

_EDITABLE_STATUSES = (PolicyStatus.DRAFT.value, PolicyStatus.REVIEW.value)


def _next_code(db: Session) -> str:
    last_id = db.scalar(select(Policy.id).order_by(Policy.id.desc()).limit(1)) or 0
    return f"POL-{last_id + 1:03d}"


def _get_policy(db: Session, policy_id: int) -> Policy:
    policy = db.get(
        Policy,
        policy_id,
        options=[
            selectinload(Policy.versions).selectinload(PolicyVersion.approvals),
            selectinload(Policy.versions).selectinload(PolicyVersion.acks),
            selectinload(Policy.controls),
        ],
    )
    if policy is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Політику не знайдено")
    return policy


def _out(policy: Policy) -> PolicyOut:
    data = PolicyOut.model_validate(policy)
    if policy.current_version:
        data.current_version = PolicyVersionOut.model_validate(policy.current_version)
    return data


@router.get("", response_model=list[PolicyListItem])
def list_policies(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    system_id: int | None = None,
):
    query = select(Policy)
    if system_id:
        query = query.where(
            Policy.systems.any(InformationSystem.id == system_id) | ~Policy.systems.any()
        )
    policies = db.scalars(
        query.options(
            selectinload(Policy.versions).selectinload(PolicyVersion.approvals),
            selectinload(Policy.versions).selectinload(PolicyVersion.acks),
        ).order_by(Policy.id)
    ).all()
    result = []
    for policy in policies:
        item = PolicyListItem.model_validate(policy)
        version = policy.current_version
        if version:
            item.version_number = version.number
            item.ack_total = len(version.acks)
            item.ack_done = sum(1 for a in version.acks if a.acknowledged_at)
            item.pending_my_approval = policy.status == PolicyStatus.APPROVAL.value and any(
                a.approver_id == actor.id and a.decision == ApprovalDecision.PENDING.value
                for a in version.approvals
            )
            item.pending_my_ack = any(
                a.user_id == actor.id and a.acknowledged_at is None for a in version.acks
            )
        result.append(item)
    return result


@router.post("", response_model=PolicyOut, status_code=status.HTTP_201_CREATED)
def create_policy(
    body: PolicyIn, db: Session = Depends(get_db), actor: User = Depends(require_policy_manager)
):
    policy = Policy(
        code=_next_code(db),
        title=body.title,
        owner_id=body.owner_id or actor.id,
        next_review_date=body.next_review_date,
    )
    policy.controls = list(
        db.scalars(select(Control).where(Control.id.in_(body.control_ids))).all()
    )
    policy.systems = list(
        db.scalars(
            select(InformationSystem).where(InformationSystem.id.in_(body.system_ids))
        ).all()
    )
    policy.versions.append(PolicyVersion(number=1, created_by_id=actor.id))
    db.add(policy)
    db.flush()
    log_action(db, actor, "create", "policy", policy.id, {"code": policy.code})
    db.commit()
    return _out(_get_policy(db, policy.id))


@router.get("/{policy_id}", response_model=PolicyOut)
def get_policy(
    policy_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    return _out(_get_policy(db, policy_id))


@router.put("/{policy_id}", response_model=PolicyOut)
def update_policy(
    policy_id: int,
    body: PolicyIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_policy_manager),
):
    policy = _get_policy(db, policy_id)
    policy.title = body.title
    policy.owner_id = body.owner_id
    policy.next_review_date = body.next_review_date
    policy.controls = list(
        db.scalars(select(Control).where(Control.id.in_(body.control_ids))).all()
    )
    policy.systems = list(
        db.scalars(
            select(InformationSystem).where(InformationSystem.id.in_(body.system_ids))
        ).all()
    )
    log_action(db, actor, "update", "policy", policy.id, {"code": policy.code})
    db.commit()
    return _out(_get_policy(db, policy_id))


@router.put("/{policy_id}/content", response_model=PolicyOut)
def update_content(
    policy_id: int,
    body: PolicyContentIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_policy_manager),
):
    policy = _get_policy(db, policy_id)
    if policy.status not in _EDITABLE_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Текст можна редагувати лише в статусах «чернетка» або «переглядається»",
        )
    policy.current_version.content_md = body.content_md
    log_action(db, actor, "update_content", "policy", policy.id, {"code": policy.code})
    db.commit()
    return _out(_get_policy(db, policy_id))


@router.post("/{policy_id}/file", response_model=PolicyOut)
def upload_file(
    policy_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: User = Depends(require_policy_manager),
):
    policy = _get_policy(db, policy_id)
    if policy.status not in _EDITABLE_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, "Файл можна змінювати лише в чернетці")
    settings = get_settings()
    contents = file.file.read()
    if len(contents) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Файл завеликий (ліміт {settings.max_upload_mb} МБ)",
        )
    os.makedirs(settings.upload_dir, exist_ok=True)
    safe_name = os.path.basename(file.filename or "policy")
    stored = f"{uuid.uuid4().hex}_{safe_name}"
    with open(os.path.join(settings.upload_dir, stored), "wb") as fh:
        fh.write(contents)
    version = policy.current_version
    version.file_name = safe_name
    version.file_path = stored
    log_action(db, actor, "upload_file", "policy", policy.id, {"file": safe_name})
    db.commit()
    return _out(_get_policy(db, policy_id))


@router.get("/{policy_id}/versions/{version_id}/file")
def download_file(
    policy_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    version = db.get(PolicyVersion, version_id)
    if version is None or version.policy_id != policy_id or not version.file_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Файл не знайдено")
    path = os.path.join(get_settings().upload_dir, version.file_path)
    if not os.path.isfile(path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Файл відсутній на диску")
    return FileResponse(path, filename=version.file_name or "policy")


@router.get("/{policy_id}/versions/{version_id}", response_model=PolicyVersionOut)
def get_version(
    policy_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    version = db.get(
        PolicyVersion,
        version_id,
        options=[selectinload(PolicyVersion.approvals), selectinload(PolicyVersion.acks)],
    )
    if version is None or version.policy_id != policy_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Версію не знайдено")
    return version


# --- Workflow ---

@router.post("/{policy_id}/submit", response_model=PolicyOut)
def submit_for_approval(
    policy_id: int,
    body: SubmitApprovalIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_policy_manager),
):
    policy = _get_policy(db, policy_id)
    if policy.status not in _EDITABLE_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "На погодження можна подати лише чернетку"
        )
    version = policy.current_version
    if not version.content_md and not version.file_path:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Додайте текст політики або файл перед погодженням"
        )
    approvers = db.scalars(
        select(User).where(User.id.in_(body.approver_ids), User.is_active)
    ).all()
    if len(approvers) != len(set(body.approver_ids)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Деяких погоджувачів не знайдено")
    version.approvals.clear()
    for approver in approvers:
        version.approvals.append(PolicyApproval(approver_id=approver.id))
    policy.status = PolicyStatus.APPROVAL.value
    log_action(
        db, actor, "submit_approval", "policy", policy.id,
        {"approvers": [a.email for a in approvers]},
    )
    db.commit()
    for approver in approvers:
        if approver.id != actor.id:
            notify_user(
                approver,
                f"GRC: політика {policy.code} очікує вашого погодження",
                f"Політику {policy.code} — {policy.title} подано на погодження.",
            )
    return _out(_get_policy(db, policy_id))


@router.post("/{policy_id}/decide", response_model=PolicyOut)
def decide(
    policy_id: int,
    body: DecisionIn,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    policy = _get_policy(db, policy_id)
    if policy.status != PolicyStatus.APPROVAL.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "Політика не на погодженні")
    if body.decision == ApprovalDecision.PENDING:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Оберіть рішення")
    version = policy.current_version
    approval = next(
        (
            a
            for a in version.approvals
            if a.approver_id == actor.id and a.decision == ApprovalDecision.PENDING.value
        ),
        None,
    )
    if approval is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ви не є погоджувачем цієї версії")

    approval.decision = body.decision.value
    approval.comment = body.comment
    approval.decided_at = datetime.now(timezone.utc)

    if body.decision == ApprovalDecision.REJECTED:
        policy.status = PolicyStatus.DRAFT.value
    elif all(a.decision == ApprovalDecision.APPROVED.value for a in version.approvals):
        policy.status = PolicyStatus.APPROVED.value
        version.approved_at = datetime.now(timezone.utc)

    log_action(
        db, actor, "decide", "policy", policy.id,
        {"decision": body.decision.value, "version": version.number},
    )
    db.commit()
    if policy.owner_id and policy.owner_id != actor.id:
        decision_ua = "погоджено" if body.decision == ApprovalDecision.APPROVED else "відхилено"
        notify_user(
            db.get(User, policy.owner_id),
            f"GRC: рішення щодо політики {policy.code}",
            f"{actor.full_name}: {decision_ua} політику {policy.code} — {policy.title}."
            + (f"\nКоментар: {body.comment}" if body.comment else ""),
        )
    return _out(_get_policy(db, policy_id))


@router.post("/{policy_id}/activate", response_model=PolicyOut)
def activate(
    policy_id: int, db: Session = Depends(get_db), actor: User = Depends(require_policy_manager)
):
    policy = _get_policy(db, policy_id)
    if policy.status != PolicyStatus.APPROVED.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "Активувати можна лише затверджену політику")
    policy.status = PolicyStatus.ACTIVE.value
    policy.current_version.activated_at = datetime.now(timezone.utc)
    log_action(db, actor, "activate", "policy", policy.id, {"code": policy.code})
    db.commit()
    return _out(_get_policy(db, policy_id))


@router.post("/{policy_id}/new-version", response_model=PolicyOut)
def new_version(
    policy_id: int, db: Session = Depends(get_db), actor: User = Depends(require_policy_manager)
):
    """Створює нову редакцію (статус «переглядається»); попередня версія лишається в історії."""
    policy = _get_policy(db, policy_id)
    if policy.status not in (PolicyStatus.ACTIVE.value, PolicyStatus.ARCHIVED.value):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Нову версію можна створити лише для діючої політики"
        )
    current = policy.current_version
    policy.versions.append(
        PolicyVersion(
            number=current.number + 1,
            content_md=current.content_md,
            created_by_id=actor.id,
        )
    )
    policy.status = PolicyStatus.REVIEW.value
    log_action(db, actor, "new_version", "policy", policy.id, {"number": current.number + 1})
    db.commit()
    return _out(_get_policy(db, policy_id))


@router.post("/{policy_id}/archive", response_model=PolicyOut)
def archive(
    policy_id: int, db: Session = Depends(get_db), actor: User = Depends(require_policy_manager)
):
    policy = _get_policy(db, policy_id)
    policy.status = PolicyStatus.ARCHIVED.value
    log_action(db, actor, "archive", "policy", policy.id, {"code": policy.code})
    db.commit()
    return _out(_get_policy(db, policy_id))


# --- Ознайомлення ---

@router.post("/{policy_id}/acks", response_model=PolicyOut)
def assign_acks(
    policy_id: int,
    body: AssignAcksIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_policy_manager),
):
    policy = _get_policy(db, policy_id)
    if policy.status != PolicyStatus.ACTIVE.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ознайомлення призначається лише для діючої політики"
        )
    version = policy.current_version
    existing = {a.user_id for a in version.acks}
    users = db.scalars(select(User).where(User.id.in_(body.user_ids), User.is_active)).all()
    added = 0
    for target in users:
        if target.id not in existing:
            version.acks.append(PolicyAck(user_id=target.id))
            added += 1
    log_action(db, actor, "assign_acks", "policy", policy.id, {"added": added})
    db.commit()
    for target in users:
        if target.id in existing or target.id == actor.id:
            continue
        notify_user(
            target,
            f"GRC: ознайомтеся з політикою {policy.code}",
            f"Вам призначено ознайомлення з політикою {policy.code} — {policy.title}. "
            f"Підтвердьте ознайомлення в системі.",
        )
    return _out(_get_policy(db, policy_id))


@router.post("/{policy_id}/acknowledge", response_model=PolicyOut)
def acknowledge(
    policy_id: int, db: Session = Depends(get_db), actor: User = Depends(get_current_user)
):
    policy = _get_policy(db, policy_id)
    version = policy.current_version
    ack = next(
        (a for a in version.acks if a.user_id == actor.id and a.acknowledged_at is None),
        None,
    )
    if ack is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Вам не призначено ознайомлення з цією політикою"
        )
    ack.acknowledged_at = datetime.now(timezone.utc)
    log_action(db, actor, "acknowledge", "policy", policy.id, {"version": version.number})
    db.commit()
    return _out(_get_policy(db, policy_id))


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_policy(
    policy_id: int, db: Session = Depends(get_db), actor: User = Depends(require_policy_manager)
):
    policy = _get_policy(db, policy_id)
    if policy.status != PolicyStatus.DRAFT.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Видалити можна лише чернетку. Для виведення з обігу використайте архівування",
        )
    log_action(db, actor, "delete", "policy", policy.id, {"code": policy.code})
    db.delete(policy)
    db.commit()
