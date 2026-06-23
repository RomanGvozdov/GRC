"""Скидання пароля адміністратором (UI «Скинути пароль» → PATCH /users/{id})."""

import pyotp

from tests.conftest import full_login


def _make_reader(client, admin_headers, email):
    client.post(
        "/api/users",
        json={"email": email, "full_name": "Reset Тест", "password": "Zk9#vLm2@qRt7w",
              "role": "reader"},
        headers=admin_headers,
    )
    users = client.get("/api/users", headers=admin_headers).json()
    return next(u for u in users if u["email"] == email)


def test_admin_resets_password_invalidates_sessions(client, admin_headers):
    user = _make_reader(client, admin_headers, "resetme@example.com")
    auth = full_login(client, "resetme@example.com", "Zk9#vLm2@qRt7w")
    old_headers = {"Authorization": f"Bearer {auth['tokens']['access_token']}"}
    assert client.get("/api/auth/me", headers=old_headers).status_code == 200

    # Слабкий/словниковий пароль — відмова
    assert client.patch(
        f"/api/users/{user['id']}", json={"password": "password12345"}, headers=admin_headers
    ).status_code == 400
    # Закороткий — валідація схеми
    assert client.patch(
        f"/api/users/{user['id']}", json={"password": "short"}, headers=admin_headers
    ).status_code == 422

    # Надійний новий пароль — успіх
    assert client.patch(
        f"/api/users/{user['id']}", json={"password": "Rt7$wQn4#pLm2x"}, headers=admin_headers
    ).status_code == 200

    # Старі сесії анульовано (token_version інкрементовано)
    assert client.get("/api/auth/me", headers=old_headers).status_code == 401

    # Вхід із новим паролем працює (2FA збережена — потрібен код TOTP)
    resp = client.post(
        "/api/auth/login",
        json={
            "email": "resetme@example.com",
            "password": "Rt7$wQn4#pLm2x",
            "totp_code": pyotp.TOTP(auth["totp_secret"]).now(),
        },
    ).json()
    assert resp["status"] == "ok"
    new_headers = {"Authorization": f"Bearer {resp['tokens']['access_token']}"}
    assert client.get("/api/auth/me", headers=new_headers).status_code == 200
