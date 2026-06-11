import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet

from app.config import get_settings

_ph = PasswordHasher()  # Argon2id за замовчуванням


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, password)
    except VerifyMismatchError:
        return False


# --- Шифрування TOTP-секретів у БД (Fernet з ключем, похідним від SECRET_KEY) ---

def _fernet() -> Fernet:
    key = hashlib.sha256(get_settings().secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()


# --- TOTP ---

def generate_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(secret: str, email: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name="GRC")


def verify_totp(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def generate_recovery_codes(n: int = 8) -> list[str]:
    return [secrets.token_hex(5) for _ in range(n)]


def hash_recovery_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


# --- JWT ---
# scope: "full" — повний доступ; "totp_setup" — лише налаштування 2FA після першого входу

def create_token(user_id: int, token_version: int, scope: str, ttl: timedelta,
                 token_type: str = "access") -> str:
    settings = get_settings()
    payload = {
        "sub": str(user_id),
        "ver": token_version,
        "scope": scope,
        "type": token_type,
        "exp": datetime.now(timezone.utc) + ttl,
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def create_access_token(user_id: int, token_version: int, scope: str = "full") -> str:
    return create_token(
        user_id, token_version, scope,
        timedelta(minutes=get_settings().access_token_ttl_minutes), "access",
    )


def create_refresh_token(user_id: int, token_version: int) -> str:
    return create_token(
        user_id, token_version, "full",
        timedelta(days=get_settings().refresh_token_ttl_days), "refresh",
    )


def decode_token(token: str) -> dict:
    return jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
