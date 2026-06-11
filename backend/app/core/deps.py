import hashlib
from datetime import datetime, timezone

import jwt as pyjwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import can_edit_entity as _can_edit
from app.core.permissions import has_permission
from app.core.security import decode_token
from app.database import get_db
from app.models import APIToken, User

_bearer = HTTPBearer(auto_error=False)

API_TOKEN_PREFIX = "grc_"


def _user_from_api_token(token: str, db: Session) -> User:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    record = db.scalar(select(APIToken).where(APIToken.token_hash == token_hash))
    if record is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Недійсний API-токен")
    if record.expires_at:
        expires = record.expires_at
        if expires.tzinfo is None:  # SQLite повертає naive datetime
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < datetime.now(timezone.utc):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Термін дії API-токена минув")
    user = db.get(User, record.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Користувача токена деактивовано")
    record.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return user


def _get_user_from_token(token: str, db: Session, required_scope: str = "full") -> User:
    if token.startswith(API_TOKEN_PREFIX):
        return _user_from_api_token(token, db)

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


def require_permission(module: str, level: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        if not has_permission(user, module, level):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Недостатньо прав")
        return user

    return checker


# Адміністрування: користувачі, довідники, каталоги, ролі, токени
require_admin = require_permission("admin", "manage")


def can_edit_entity(user: User, owner_id: int | None, module: str) -> bool:
    return _can_edit(user, owner_id, module)
