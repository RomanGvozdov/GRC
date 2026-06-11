import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.core.deps import can_edit_entity, get_current_user, require_manager
from app.database import get_db
from app.models import Control, Evidence, ImplementationStatus, Requirement, User
from app.schemas import ControlIn, ControlListItem, ControlOut, EvidenceLinkIn, EvidenceOut
from app.services.audit import log_action

router = APIRouter(prefix="/controls", tags=["controls"])


def next_code(db: Session) -> str:
    last_id = db.scalar(select(Control.id).order_by(Control.id.desc()).limit(1)) or 0
    return f"CTRL-{last_id + 1:03d}"


def _get_control(db: Session, control_id: int) -> Control:
    control = db.get(
        Control,
        control_id,
        options=[selectinload(Control.requirements), selectinload(Control.evidence)],
    )
    if control is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Контроль не знайдено")
    return control


def _apply_body(db: Session, control: Control, body: ControlIn) -> None:
    if (
        body.implementation_status == ImplementationStatus.NOT_APPLICABLE
        and not body.na_justification
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            'Статус "не застосовно" вимагає обґрунтування (основа для SoA)',
        )
    control.name = body.name
    control.description = body.description
    control.control_type = body.control_type.value if body.control_type else None
    control.owner_id = body.owner_id
    control.implementation_status = body.implementation_status.value
    control.na_justification = body.na_justification
    control.review_period_months = body.review_period_months
    control.next_review_date = body.next_review_date

    requirements = db.scalars(
        select(Requirement).where(Requirement.id.in_(body.requirement_ids))
    ).all()
    if len(requirements) != len(set(body.requirement_ids)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Деякі вимоги не знайдено")
    control.requirements = list(requirements)


@router.get("", response_model=list[ControlListItem])
def list_controls(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    status_filter: ImplementationStatus | None = Query(default=None, alias="status"),
    framework_id: int | None = None,
    owner_id: int | None = None,
    search: str | None = None,
):
    query = select(Control).options(
        selectinload(Control.requirements), selectinload(Control.owner)
    )
    if status_filter:
        query = query.where(Control.implementation_status == status_filter.value)
    if owner_id:
        query = query.where(Control.owner_id == owner_id)
    if search:
        pattern = f"%{search}%"
        query = query.where(Control.name.ilike(pattern) | Control.code.ilike(pattern))
    if framework_id:
        query = query.where(
            Control.requirements.any(Requirement.framework_id == framework_id)
        )
    return db.scalars(query.order_by(Control.id)).all()


@router.post("", response_model=ControlOut, status_code=status.HTTP_201_CREATED)
def create_control(
    body: ControlIn, db: Session = Depends(get_db), actor: User = Depends(require_manager)
):
    control = Control(code=next_code(db))
    _apply_body(db, control, body)
    db.add(control)
    db.flush()
    log_action(db, actor, "create", "control", control.id, {"code": control.code})
    db.commit()
    return _get_control(db, control.id)


@router.get("/{control_id}", response_model=ControlOut)
def get_control(
    control_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    return _get_control(db, control_id)


@router.put("/{control_id}", response_model=ControlOut)
def update_control(
    control_id: int,
    body: ControlIn,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    control = _get_control(db, control_id)
    if not can_edit_entity(actor, control.owner_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ви не є відповідальним за цей контроль")
    _apply_body(db, control, body)
    log_action(db, actor, "update", "control", control.id, {"code": control.code})
    db.commit()
    return _get_control(db, control_id)


@router.delete("/{control_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_control(
    control_id: int, db: Session = Depends(get_db), actor: User = Depends(require_manager)
):
    control = _get_control(db, control_id)
    log_action(db, actor, "delete", "control", control.id, {"code": control.code})
    db.delete(control)
    db.commit()


# --- Evidence ---

def _check_evidence_access(actor: User, control: Control) -> None:
    if not can_edit_entity(actor, control.owner_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ви не є відповідальним за цей контроль")


@router.post("/{control_id}/evidence/link", response_model=EvidenceOut, status_code=201)
def add_evidence_link(
    control_id: int,
    body: EvidenceLinkIn,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    control = _get_control(db, control_id)
    _check_evidence_access(actor, control)
    item = Evidence(
        control_id=control.id,
        kind="link",
        name=body.name,
        url=body.url,
        valid_until=body.valid_until,
        uploaded_by_id=actor.id,
    )
    db.add(item)
    db.flush()
    log_action(db, actor, "add_evidence", "control", control.id, {"name": body.name})
    db.commit()
    return db.get(Evidence, item.id)


@router.post("/{control_id}/evidence/file", response_model=EvidenceOut, status_code=201)
def add_evidence_file(
    control_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    control = _get_control(db, control_id)
    _check_evidence_access(actor, control)

    settings = get_settings()
    contents = file.file.read()
    if len(contents) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Файл завеликий (ліміт {settings.max_upload_mb} МБ)",
        )
    os.makedirs(settings.upload_dir, exist_ok=True)
    safe_name = os.path.basename(file.filename or "file")
    stored = f"{uuid.uuid4().hex}_{safe_name}"
    with open(os.path.join(settings.upload_dir, stored), "wb") as fh:
        fh.write(contents)

    item = Evidence(
        control_id=control.id,
        kind="file",
        name=safe_name,
        file_path=stored,
        uploaded_by_id=actor.id,
    )
    db.add(item)
    db.flush()
    log_action(db, actor, "add_evidence", "control", control.id, {"name": safe_name})
    db.commit()
    return db.get(Evidence, item.id)


@router.get("/{control_id}/evidence/{evidence_id}/download")
def download_evidence(
    control_id: int,
    evidence_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    item = db.get(Evidence, evidence_id)
    if item is None or item.control_id != control_id or item.kind != "file":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Файл не знайдено")
    path = os.path.join(get_settings().upload_dir, item.file_path)
    if not os.path.isfile(path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Файл відсутній на диску")
    return FileResponse(path, filename=item.name)


@router.delete("/{control_id}/evidence/{evidence_id}", status_code=204)
def delete_evidence(
    control_id: int,
    evidence_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    control = _get_control(db, control_id)
    _check_evidence_access(actor, control)
    item = db.get(Evidence, evidence_id)
    if item is None or item.control_id != control_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Доказ не знайдено")
    if item.kind == "file" and item.file_path:
        path = os.path.join(get_settings().upload_dir, item.file_path)
        if os.path.isfile(path):
            os.remove(path)
    log_action(db, actor, "delete_evidence", "control", control.id, {"name": item.name})
    db.delete(item)
    db.commit()
