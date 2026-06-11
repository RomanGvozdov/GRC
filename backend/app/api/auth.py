from datetime import datetime, timedelta, timezone

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.passwords import validate_password
from app.core.deps import get_current_user, get_totp_setup_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    decrypt_secret,
    encrypt_secret,
    generate_recovery_codes,
    generate_totp_secret,
    hash_password,
    hash_recovery_code,
    totp_uri,
    verify_password,
    verify_totp,
)
from app.database import get_db
from app.models import RecoveryCode, User
from app.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    TokenPair,
    TotpSetupResponse,
    TotpVerifyRequest,
    TotpVerifyResponse,
    UserOut,
)
from app.services.audit import log_action

router = APIRouter(prefix="/auth", tags=["auth"])

_BAD_CREDENTIALS = "Невірний email, пароль або код 2FA"


def _token_pair(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user.id, user.token_version),
        refresh_token=create_refresh_token(user.id, user.token_version),
    )


def _check_lockout(user: User) -> None:
    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise HTTPException(
            status.HTTP_423_LOCKED,
            "Акаунт тимчасово заблоковано через невдалі спроби входу",
        )


def _register_failure(db: Session, user: User) -> None:
    settings = get_settings()
    user.failed_logins += 1
    if user.failed_logins >= settings.max_failed_logins:
        user.locked_until = datetime.now(timezone.utc) + timedelta(
            minutes=settings.lockout_minutes
        )
        user.failed_logins = 0
        log_action(db, user, "account_locked", "user", user.id)
    db.commit()


def _try_recovery_code(db: Session, user: User, code: str) -> bool:
    code_hash = hash_recovery_code(code.strip().lower())
    rc = db.scalar(
        select(RecoveryCode).where(
            RecoveryCode.user_id == user.id,
            RecoveryCode.code_hash == code_hash,
            RecoveryCode.used_at.is_(None),
        )
    )
    if rc is None:
        return False
    rc.used_at = datetime.now(timezone.utc)
    return True


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _BAD_CREDENTIALS)

    _check_lockout(user)

    if not verify_password(body.password, user.hashed_password):
        _register_failure(db, user)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _BAD_CREDENTIALS)

    if not user.totp_enabled:
        # Перший вхід: видаємо обмежений токен лише для налаштування 2FA
        setup_token = create_access_token(user.id, user.token_version, scope="totp_setup")
        return LoginResponse(status="totp_setup_required", setup_token=setup_token)

    ok = False
    if body.totp_code:
        ok = verify_totp(decrypt_secret(user.totp_secret_encrypted), body.totp_code)
    elif body.recovery_code:
        ok = _try_recovery_code(db, user, body.recovery_code)
    if not ok:
        _register_failure(db, user)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _BAD_CREDENTIALS)

    user.failed_logins = 0
    user.locked_until = None
    log_action(db, user, "login", "user", user.id)
    db.commit()
    return LoginResponse(status="ok", tokens=_token_pair(user))


@router.post("/totp/setup", response_model=TotpSetupResponse)
def totp_setup(
    db: Session = Depends(get_db), user: User = Depends(get_totp_setup_user)
):
    if user.totp_enabled:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "2FA вже налаштовано")
    secret = generate_totp_secret()
    user.totp_secret_encrypted = encrypt_secret(secret)
    db.commit()
    return TotpSetupResponse(secret=secret, otpauth_uri=totp_uri(secret, user.email))


@router.post("/totp/verify", response_model=TotpVerifyResponse)
def totp_verify(
    body: TotpVerifyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_totp_setup_user),
):
    if user.totp_enabled:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "2FA вже налаштовано")
    if not user.totp_secret_encrypted:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Спочатку викличте /auth/totp/setup")
    if not verify_totp(decrypt_secret(user.totp_secret_encrypted), body.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Невірний код. Спробуйте ще раз")

    user.totp_enabled = True
    codes = generate_recovery_codes()
    for code in codes:
        db.add(RecoveryCode(user_id=user.id, code_hash=hash_recovery_code(code)))
    log_action(db, user, "totp_enabled", "user", user.id)
    db.commit()
    return TotpVerifyResponse(tokens=_token_pair(user), recovery_codes=codes)


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
    except pyjwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Недійсний refresh-токен")
    if payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Очікується refresh-токен")
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active or payload.get("ver") != user.token_version:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Токен анульовано")
    return _token_pair(user)


@router.post("/logout-all")
def logout_all(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    user.token_version += 1
    log_action(db, user, "logout_all", "user", user.id)
    db.commit()
    return {"detail": "Усі сесії завершено"}


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Невірний поточний пароль")
    if (problem := validate_password(body.new_password)) is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, problem)
    user.hashed_password = hash_password(body.new_password)
    user.token_version += 1
    log_action(db, user, "password_changed", "user", user.id)
    db.commit()
    return {"detail": "Пароль змінено. Увійдіть знову"}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
