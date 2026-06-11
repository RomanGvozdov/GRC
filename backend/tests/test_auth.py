import pyotp

from tests.conftest import full_login


def test_login_requires_totp_after_setup(client, admin_auth):
    # Після налаштування 2FA вхід без коду має бути відхилений
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "admin-password-123"},
    )
    assert response.status_code == 401

    code = pyotp.TOTP(admin_auth["totp_secret"]).now()
    response = client.post(
        "/api/auth/login",
        json={
            "email": "admin@example.com",
            "password": "admin-password-123",
            "totp_code": code,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_me(client, admin_headers):
    response = client.get("/api/auth/me", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "admin@example.com"
    assert body["role"] == "admin"
    assert body["totp_enabled"] is True


def test_wrong_password_rejected(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "wrong-password-xxx"},
    )
    assert response.status_code == 401


def test_recovery_code_login(client, admin_auth):
    code = admin_auth["recovery_codes"][0]
    response = client.post(
        "/api/auth/login",
        json={
            "email": "admin@example.com",
            "password": "admin-password-123",
            "recovery_code": code,
        },
    )
    assert response.status_code == 200

    # Повторне використання того ж коду — відмова
    response = client.post(
        "/api/auth/login",
        json={
            "email": "admin@example.com",
            "password": "admin-password-123",
            "recovery_code": code,
        },
    )
    assert response.status_code == 401


def test_refresh_token(client, admin_auth):
    response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": admin_auth["tokens"]["refresh_token"]},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_create_user_and_role_enforcement(client, admin_headers):
    response = client.post(
        "/api/users",
        json={
            "email": "reader@example.com",
            "full_name": "Читач Тестовий",
            "password": "reader-password-123",
            "role": "reader",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text

    reader = full_login(client, "reader@example.com", "reader-password-123")
    reader_headers = {"Authorization": f"Bearer {reader['tokens']['access_token']}"}

    # Читач не може створювати користувачів
    response = client.post(
        "/api/users",
        json={
            "email": "x@example.com",
            "full_name": "X",
            "password": "x-password-123456",
            "role": "reader",
        },
        headers=reader_headers,
    )
    assert response.status_code == 403

    # Читач не може створювати ризики
    response = client.post("/api/risks", json={"title": "Тест"}, headers=reader_headers)
    assert response.status_code == 403

    # Але може переглядати
    response = client.get("/api/risks", headers=reader_headers)
    assert response.status_code == 200
