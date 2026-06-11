from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import require_permission

require_log_reader = require_permission("audit_log", "read")
from app.database import get_db
from app.models import AuditLogEntry, User
from app.schemas import AuditEntryOut

router = APIRouter(prefix="/audit-log", tags=["audit"])


@router.get("", response_model=list[AuditEntryOut])
def list_audit_log(
    db: Session = Depends(get_db),
    _: User = Depends(require_log_reader),
    entity_type: str | None = None,
    user_id: int | None = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
):
    query = select(AuditLogEntry).options(selectinload(AuditLogEntry.user))
    if entity_type:
        query = query.where(AuditLogEntry.entity_type == entity_type)
    if user_id:
        query = query.where(AuditLogEntry.user_id == user_id)
    return db.scalars(
        query.order_by(AuditLogEntry.id.desc()).limit(limit).offset(offset)
    ).all()
