import jwt as pyjwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.database import get_db
from app.models import Role, User

_bearer = HTTPBearer(auto_error=False)


def _get_user_from_token(token: str, db: Session, required_scope: str = "full") -> User:
    try:
        payload = decode_token(token)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Термін дії токена минув")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Недійсний токен")

    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Очікується access-токен")
    if required_scope == "full" and payload.get("scope") != "full":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Потрібно завершити налаштування 2FA")

    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Користувача не знайдено або деактивовано")
    if payload.get("ver") != user.token_version:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Токен анульовано")
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Не автентифіковано")
    return _get_user_from_token(credentials.credentials, db)


def get_totp_setup_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Допускає токени з обмеженим scope=totp_setup (перший вхід)."""
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Не автентифіковано")
    return _get_user_from_token(credentials.credentials, db, required_scope="totp_setup")


def require_roles(*roles: Role):
    allowed = {r.value for r in roles}

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Недостатньо прав")
        return user

    return checker


# Ролі, що можуть створювати/керувати об'єктами модулів
require_manager = require_roles(Role.ADMIN, Role.GRC_MANAGER)
require_admin = require_roles(Role.ADMIN)


def can_edit_entity(user: User, owner_id: int | None) -> bool:
    """Виконавець редагує лише призначені йому об'єкти; менеджер і адмін — будь-які."""
    if user.role in (Role.ADMIN.value, Role.GRC_MANAGER.value):
        return True
    if user.role == Role.EXECUTOR.value:
        return owner_id == user.id
    return False
