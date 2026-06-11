from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.core.passwords import validate_password
from app.core.security import hash_password
from app.database import get_db
from app.models import RecoveryCode, User
from app.schemas import UserCreate, UserOut, UserUpdate
from app.services.audit import log_action

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.scalars(select(User).order_by(User.full_name)).all()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate, db: Session = Depends(get_db), actor: User = Depends(require_admin)
):
    if (problem := validate_password(body.password)) is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, problem)
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Користувач з таким email вже існує")
    user = User(
        email=email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role=body.role.value,
    )
    db.add(user)
    db.flush()
    log_action(db, actor, "create", "user", user.id, {"email": email, "role": body.role.value})
    db.commit()
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Користувача не знайдено")

    changes: dict = {}
    if body.full_name is not None:
        user.full_name = body.full_name
        changes["full_name"] = body.full_name
    if body.role is not None:
        user.role = body.role.value
        changes["role"] = body.role.value
    if body.is_active is not None:
        if user.id == actor.id and not body.is_active:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Не можна деактивувати себе")
        user.is_active = body.is_active
        changes["is_active"] = body.is_active
        if not body.is_active:
            user.token_version += 1
    if body.password is not None:
        if (problem := validate_password(body.password)) is not None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, problem)
        user.hashed_password = hash_password(body.password)
        user.token_version += 1
        changes["password"] = "reset"
    if body.reset_totp:
        user.totp_enabled = False
        user.totp_secret_encrypted = None
        user.token_version += 1
        db.query(RecoveryCode).filter(RecoveryCode.user_id == user.id).delete()
        changes["totp"] = "reset"

    log_action(db, actor, "update", "user", user.id, changes)
    db.commit()
    return user
