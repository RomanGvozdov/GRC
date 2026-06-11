import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import require_admin
from app.core.permissions import LEVELS, MODULES
from app.database import get_db
from app.models import APIToken, CustomRole, User
from app.schemas_phase3 import (
    APITokenCreated,
    APITokenIn,
    APITokenOut,
    CustomRoleIn,
    CustomRoleOut,
    PermissionsMeta,
)
from app.services.audit import log_action

router = APIRouter(tags=["rbac"])


@router.get("/permissions-meta", response_model=PermissionsMeta)
def permissions_meta(_: User = Depends(require_admin)):
    return PermissionsMeta(modules=MODULES, levels=LEVELS)


# --- Кастомні ролі ---

def _validate_permissions(permissions: dict[str, str]) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for module, level in permissions.items():
        if module not in MODULES:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Невідомий модуль: {module}")
        if level not in LEVELS:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Невідомий рівень: {level}")
        cleaned[module] = level
    return cleaned


@router.get("/roles", response_model=list[CustomRoleOut])
def list_roles(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.scalars(select(CustomRole).order_by(CustomRole.name)).all()


@router.post("/roles", response_model=CustomRoleOut, status_code=status.HTTP_201_CREATED)
def create_role(
    body: CustomRoleIn, db: Session = Depends(get_db), actor: User = Depends(require_admin)
):
    if db.scalar(select(CustomRole).where(CustomRole.name == body.name)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Роль з такою назвою вже існує")
    role = CustomRole(name=body.name, permissions=_validate_permissions(body.permissions))
    db.add(role)
    db.flush()
    log_action(db, actor, "create", "custom_role", role.id, {"name": body.name})
    db.commit()
    return role


@router.put("/roles/{role_id}", response_model=CustomRoleOut)
def update_role(
    role_id: int,
    body: CustomRoleIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    role = db.get(CustomRole, role_id)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Роль не знайдено")
    role.name = body.name
    role.permissions = _validate_permissions(body.permissions)
    log_action(db, actor, "update", "custom_role", role.id, {"name": body.name})
    db.commit()
    return role


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: int, db: Session = Depends(get_db), actor: User = Depends(require_admin)
):
    role = db.get(CustomRole, role_id)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Роль не знайдено")
    in_use = db.scalar(select(User.id).where(User.custom_role_id == role_id).limit(1))
    if in_use:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Роль призначена користувачам і не може бути видалена"
        )
    log_action(db, actor, "delete", "custom_role", role.id, {"name": role.name})
    db.delete(role)
    db.commit()


# --- API-токени ---

@router.get("/api-tokens", response_model=list[APITokenOut])
def list_tokens(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.scalars(
        select(APIToken).options(selectinload(APIToken.user)).order_by(APIToken.id)
    ).all()


@router.post("/api-tokens", response_model=APITokenCreated, status_code=201)
def create_token(
    body: APITokenIn, db: Session = Depends(get_db), actor: User = Depends(require_admin)
):
    user = db.get(User, body.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Користувача не знайдено")

    raw = "grc_" + secrets.token_urlsafe(32)
    record = APIToken(
        user_id=user.id,
        name=body.name,
        token_prefix=raw[:12],
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        expires_at=(
            datetime.now(timezone.utc) + timedelta(days=body.expires_days)
            if body.expires_days
            else None
        ),
    )
    db.add(record)
    db.flush()
    log_action(
        db, actor, "create", "api_token", record.id,
        {"name": body.name, "user": user.email},
    )
    db.commit()
    return APITokenCreated(token=raw, item=APITokenOut.model_validate(record))


@router.delete("/api-tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_token(
    token_id: int, db: Session = Depends(get_db), actor: User = Depends(require_admin)
):
    record = db.get(APIToken, token_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Токен не знайдено")
    log_action(db, actor, "delete", "api_token", record.id, {"name": record.name})
    db.delete(record)
    db.commit()
