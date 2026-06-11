from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user
from app.database import get_db
from app.models import Comment, Control, Risk, Role, User
from app.schemas import CommentIn, CommentOut
from app.services.audit import log_action

router = APIRouter(prefix="/comments", tags=["comments"])

_ENTITY_MODELS = {"risk": Risk, "control": Control}


def _check_entity(db: Session, entity_type: str, entity_id: int) -> None:
    model = _ENTITY_MODELS.get(entity_type)
    if model is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Невідомий тип об'єкта")
    if db.get(model, entity_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Об'єкт не знайдено")


@router.get("/{entity_type}/{entity_id}", response_model=list[CommentOut])
def list_comments(
    entity_type: str = Path(pattern="^(risk|control)$"),
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
    entity_type: str = Path(pattern="^(risk|control)$"),
    entity_id: int = Path(),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    if actor.role == Role.READER.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Читач не може додавати коментарі")
    _check_entity(db, entity_type, entity_id)
    comment = Comment(
        entity_type=entity_type, entity_id=entity_id, author_id=actor.id, text=body.text
    )
    db.add(comment)
    db.flush()
    log_action(db, actor, "comment", entity_type, entity_id)
    db.commit()
    return db.get(Comment, comment.id)
