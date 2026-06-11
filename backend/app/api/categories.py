from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.database import get_db
from app.models import Risk, RiskCategory, User
from app.schemas import CategoryIn, CategoryOut
from app.services.audit import log_action

router = APIRouter(prefix="/risk-categories", tags=["dictionaries"])


@router.get("", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.scalars(select(RiskCategory).order_by(RiskCategory.name)).all()


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(
    body: CategoryIn, db: Session = Depends(get_db), actor: User = Depends(require_admin)
):
    if db.scalar(select(RiskCategory).where(RiskCategory.name == body.name)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Категорія з такою назвою вже існує")
    category = RiskCategory(name=body.name)
    db.add(category)
    db.flush()
    log_action(db, actor, "create", "risk_category", category.id, {"name": body.name})
    db.commit()
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int, db: Session = Depends(get_db), actor: User = Depends(require_admin)
):
    category = db.get(RiskCategory, category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Категорію не знайдено")
    in_use = db.scalar(select(Risk.id).where(Risk.category_id == category_id).limit(1))
    if in_use:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Категорія використовується в ризиках і не може бути видалена"
        )
    log_action(db, actor, "delete", "risk_category", category.id, {"name": category.name})
    db.delete(category)
    db.commit()
