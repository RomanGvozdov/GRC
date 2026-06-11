from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.risks import next_code as next_risk_code
from app.core.deps import can_edit_entity, get_current_user, require_permission

require_audit_manager = require_permission("audits", "manage")
require_audit_reader = require_permission("audits", "read")
from app.database import get_db
from app.models import (
    Audit,
    AuditChecklistItem,
    Finding,
    Requirement,
    Risk,
    RiskStatus,
    User,
)
from app.schemas_phase2 import (
    AuditBrief,
    AuditIn,
    AuditOut,
    ChecklistItemIn,
    ChecklistItemOut,
    ChecklistItemUpdate,
    FindingIn,
    FindingOut,
)
from app.services.audit import log_action
from app.services.notify import notify_user

router = APIRouter(prefix="/audits", tags=["audits"])


def _next_audit_code(db: Session) -> str:
    last_id = db.scalar(select(Audit.id).order_by(Audit.id.desc()).limit(1)) or 0
    return f"AUD-{last_id + 1:03d}"


def _next_finding_code(db: Session) -> str:
    last_id = db.scalar(select(Finding.id).order_by(Finding.id.desc()).limit(1)) or 0
    return f"FND-{last_id + 1:03d}"


def _get_audit(db: Session, audit_id: int) -> Audit:
    audit = db.get(
        Audit,
        audit_id,
        options=[
            selectinload(Audit.checklist),
            selectinload(Audit.findings).selectinload(Finding.risk),
        ],
    )
    if audit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Аудит не знайдено")
    return audit


def _apply(audit: Audit, body: AuditIn) -> None:
    audit.title = body.title
    audit.audit_type = body.audit_type.value
    audit.scope = body.scope
    audit.framework_id = body.framework_id
    audit.date_from = body.date_from
    audit.date_to = body.date_to
    audit.auditor_id = body.auditor_id
    audit.auditor_external = body.auditor_external
    audit.status = body.status.value


@router.get("", response_model=list[AuditBrief])
def list_audits(db: Session = Depends(get_db), _: User = Depends(require_audit_reader)):
    return db.scalars(select(Audit).order_by(Audit.id.desc())).all()


@router.post("", response_model=AuditOut, status_code=status.HTTP_201_CREATED)
def create_audit(
    body: AuditIn, db: Session = Depends(get_db), actor: User = Depends(require_audit_manager)
):
    audit = Audit(code=_next_audit_code(db))
    _apply(audit, body)
    db.add(audit)
    db.flush()
    log_action(db, actor, "create", "audit", audit.id, {"code": audit.code})
    db.commit()
    return _get_audit(db, audit.id)


@router.get("/{audit_id}", response_model=AuditOut)
def get_audit(audit_id: int, db: Session = Depends(get_db), _: User = Depends(require_audit_reader)):
    return _get_audit(db, audit_id)


@router.put("/{audit_id}", response_model=AuditOut)
def update_audit(
    audit_id: int,
    body: AuditIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_audit_manager),
):
    audit = _get_audit(db, audit_id)
    _apply(audit, body)
    log_action(db, actor, "update", "audit", audit.id, {"code": audit.code})
    db.commit()
    return _get_audit(db, audit_id)


@router.delete("/{audit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_audit(
    audit_id: int, db: Session = Depends(get_db), actor: User = Depends(require_audit_manager)
):
    audit = _get_audit(db, audit_id)
    log_action(db, actor, "delete", "audit", audit.id, {"code": audit.code})
    db.delete(audit)
    db.commit()


# --- Чек-лист ---

@router.post("/{audit_id}/checklist/generate", response_model=AuditOut)
def generate_checklist(
    audit_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_audit_manager),
):
    """Створює пункти чек-листа з вимог фреймворка аудиту (пропускає вже додані)."""
    audit = _get_audit(db, audit_id)
    if audit.framework_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "В аудиту не вказано фреймворк")
    existing = {item.requirement_id for item in audit.checklist if item.requirement_id}
    requirements = db.scalars(
        select(Requirement)
        .where(Requirement.framework_id == audit.framework_id)
        .order_by(Requirement.id)
    ).all()
    added = 0
    for req in requirements:
        if req.id in existing:
            continue
        audit.checklist.append(
            AuditChecklistItem(requirement_id=req.id, text=f"{req.code} — {req.title}")
        )
        added += 1
    log_action(db, actor, "generate_checklist", "audit", audit.id, {"added": added})
    db.commit()
    return _get_audit(db, audit_id)


@router.post("/{audit_id}/checklist", response_model=ChecklistItemOut, status_code=201)
def add_checklist_item(
    audit_id: int,
    body: ChecklistItemIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_audit_manager),
):
    audit = _get_audit(db, audit_id)
    item = AuditChecklistItem(
        audit_id=audit.id, text=body.text, requirement_id=body.requirement_id
    )
    db.add(item)
    db.flush()
    log_action(db, actor, "update", "audit", audit.id, {"checklist_item": body.text[:80]})
    db.commit()
    return db.get(AuditChecklistItem, item.id)


@router.patch("/{audit_id}/checklist/{item_id}", response_model=ChecklistItemOut)
def update_checklist_item(
    audit_id: int,
    item_id: int,
    body: ChecklistItemUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    audit = _get_audit(db, audit_id)
    # Заповнювати чек-лист може менеджер або призначений аудитор
    if not can_edit_entity(actor, audit.auditor_id, "audits"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ви не є аудитором цього аудиту")
    item = db.get(AuditChecklistItem, item_id)
    if item is None or item.audit_id != audit_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пункт не знайдено")
    if body.result is not None:
        item.result = body.result.value
    item.comment = body.comment
    db.commit()
    return item


@router.delete("/{audit_id}/checklist/{item_id}", status_code=204)
def delete_checklist_item(
    audit_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_audit_manager),
):
    item = db.get(AuditChecklistItem, item_id)
    if item is None or item.audit_id != audit_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пункт не знайдено")
    db.delete(item)
    db.commit()


# --- Знахідки ---

def _apply_finding(finding: Finding, body: FindingIn) -> None:
    finding.title = body.title
    finding.description = body.description
    finding.severity = body.severity.value
    finding.control_id = body.control_id
    finding.requirement_id = body.requirement_id
    finding.action_title = body.action_title
    finding.responsible_id = body.responsible_id
    finding.deadline = body.deadline
    finding.action_status = body.action_status.value


@router.post("/{audit_id}/findings", response_model=FindingOut, status_code=201)
def add_finding(
    audit_id: int,
    body: FindingIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_audit_manager),
):
    audit = _get_audit(db, audit_id)
    finding = Finding(audit_id=audit.id, code=_next_finding_code(db))
    _apply_finding(finding, body)
    db.add(finding)
    db.flush()
    log_action(db, actor, "create", "finding", finding.id, {"code": finding.code})
    db.commit()
    if finding.responsible_id and finding.responsible_id != actor.id:
        notify_user(
            db.get(User, finding.responsible_id),
            f"GRC: знахідка {finding.code} (аудит {audit.code})",
            f"Вас призначено відповідальним за коригувальну дію за знахідкою "
            f"{finding.code} — {finding.title}.",
        )
    return db.get(Finding, finding.id)


@router.put("/{audit_id}/findings/{finding_id}", response_model=FindingOut)
def update_finding(
    audit_id: int,
    finding_id: int,
    body: FindingIn,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    finding = db.get(Finding, finding_id)
    if finding is None or finding.audit_id != audit_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Знахідку не знайдено")
    # Виконавець може оновлювати знахідку, якщо відповідає за коригувальну дію
    if not can_edit_entity(actor, finding.responsible_id, "audits"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ви не відповідаєте за цю знахідку")
    _apply_finding(finding, body)
    log_action(db, actor, "update", "finding", finding.id, {"code": finding.code})
    db.commit()
    return finding


@router.delete("/{audit_id}/findings/{finding_id}", status_code=204)
def delete_finding(
    audit_id: int,
    finding_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_audit_manager),
):
    finding = db.get(Finding, finding_id)
    if finding is None or finding.audit_id != audit_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Знахідку не знайдено")
    log_action(db, actor, "delete", "finding", finding.id, {"code": finding.code})
    db.delete(finding)
    db.commit()


@router.post("/{audit_id}/findings/{finding_id}/create-risk", response_model=FindingOut)
def create_risk_from_finding(
    audit_id: int,
    finding_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_audit_manager),
):
    finding = db.get(Finding, finding_id)
    if finding is None or finding.audit_id != audit_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Знахідку не знайдено")
    if finding.risk_id is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ризик за цією знахідкою вже створено")

    risk = Risk(
        code=next_risk_code(db),
        title=finding.title,
        description=(
            f"Створено зі знахідки {finding.code} (аудит {finding.audit.code})."
            + (f"\n\n{finding.description}" if finding.description else "")
        ),
        status=RiskStatus.IDENTIFIED.value,
        owner_id=finding.responsible_id,
    )
    db.add(risk)
    db.flush()
    finding.risk_id = risk.id
    log_action(
        db, actor, "create", "risk", risk.id,
        {"code": risk.code, "from_finding": finding.code},
    )
    db.commit()
    return db.get(Finding, finding_id)
