from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user
from app.core.permissions import has_permission
from app.database import get_db
from app.models import Audit, Comment, Control, Finding, Policy, Risk, User
from app.schemas import CommentIn, CommentOut
from app.services.audit import log_action

router = APIRouter(prefix="/comments", tags=["comments"])

_ENTITY_MODELS = {
    "risk": Risk,
    "control": Control,
    "audit": Audit,
    "finding": Finding,
    "policy": Policy,
}
_ENTITY_MODULES = {
    "risk": "risks",
    "control": "controls",
    "audit": "audits",
    "finding": "audits",
    "policy": "policies",
}


def _check_entity(db: Session, entity_type: str, entity_id: int) -> None:
    model = _ENTITY_MODELS.get(entity_type)
    if model is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Невідомий тип об'єкта")
    if db.get(model, entity_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Об'єкт не знайдено")


@router.get("/{entity_type}/{entity_id}", response_model=list[CommentOut])
def list_comments(
    entity_type: str = Path(pattern="^(risk|control|audit|finding|policy)$"),
    entity_id: int = Path(),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    _check_entity(db, entity_type, entity_id)
    return db.scalars(
        select(Comment)
        .where(Comment.entity_type == entity_type, Comment.entity_id == entity_id)
        .options(selectinload(Comment.author))
        .order_by(Comment.id)
    ).all()


@router.post("/{entity_type}/{entity_id}", response_model=CommentOut, status_code=201)
def add_comment(
    body: CommentIn,
    entity_type: str = Path(pattern="^(risk|control|audit|finding|policy)$"),
    entity_id: int = Path(),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    if not has_permission(actor, _ENTITY_MODULES[entity_type], "write"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Недостатньо прав для коментування")
    _check_entity(db, entity_type, entity_id)
    comment = Comment(
        entity_type=entity_type, entity_id=entity_id, author_id=actor.id, text=body.text
    )
    db.add(comment)
    db.flush()
    log_action(db, actor, "comment", entity_type, entity_id)
    db.commit()
    return db.get(Comment, comment.id)
