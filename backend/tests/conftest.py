import os
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["ADMIN_EMAIL"] = "admin@example.com"
os.environ["ADMIN_PASSWORD"] = "admin-password-123"
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp()

import pyotp
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


def full_login(client: TestClient, email: str, password: str) -> dict:
    """Проходить повний цикл: пароль → налаштування TOTP (якщо перший вхід) → токени."""
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    data = response.json()

    if data["status"] == "totp_setup_required":
        headers = {"Authorization": f"Bearer {data['setup_token']}"}
        setup = client.post("/api/auth/totp/setup", headers=headers)
        assert setup.status_code == 200, setup.text
        secret = setup.json()["secret"]
        code = pyotp.TOTP(secret).now()
        verify = client.post("/api/auth/totp/verify", json={"code": code}, headers=headers)
        assert verify.status_code == 200, verify.text
        result = verify.json()
        return {
            "tokens": result["tokens"],
            "recovery_codes": result["recovery_codes"],
            "totp_secret": secret,
        }

    return {"tokens": data["tokens"]}


@pytest.fixture(scope="session")
def admin_auth(client):
    return full_login(client, "admin@example.com", "admin-password-123")


@pytest.fixture(scope="session")
def admin_headers(admin_auth):
    return {"Authorization": f"Bearer {admin_auth['tokens']['access_token']}"}
