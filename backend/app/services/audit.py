from sqlalchemy.orm import Session

from app.models import AuditLogEntry, User


def log_action(
    db: Session,
    user: User | None,
    action: str,
    entity_type: str,
    entity_id: int | str | None = None,
    details: dict | None = None,
) -> None:
    db.add(
        AuditLogEntry(
            user_id=user.id if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            details=details,
        )
    )
