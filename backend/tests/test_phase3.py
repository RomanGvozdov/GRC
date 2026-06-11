from datetime import date, timedelta

from tests.conftest import full_login


def test_custom_role_restricts_access(client, admin_headers):
    # Роль "тільки ризики": manage у risks, read у reports, решта none
    response = client.post(
        "/api/roles",
        json={
            "name": "Ризик-менеджер",
            "permissions": {"risks": "manage", "reports": "read", "controls": "none"},
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    role_id = response.json()["id"]

    # Користувач із кастомною роллю
    client.post(
        "/api/users",
        json={
            "email": "riskonly@example.com",
            "full_name": "Тільки Ризики",
            "password": "Xv4$pQn8#mWz2r",
            "role": "reader",
        },
        headers=admin_headers,
    )
    users = client.get("/api/users", headers=admin_headers).json()
    target = next(u for u in users if u["email"] == "riskonly@example.com")
    response = client.patch(
        f"/api/users/{target['id']}", json={"custom_role_id": role_id}, headers=admin_headers
    )
    assert response.status_code == 200
    assert response.json()["custom_role"]["name"] == "Ризик-менеджер"

    auth = full_login(client, "riskonly@example.com", "Xv4$pQn8#mWz2r")
    headers = {"Authorization": f"Bearer {auth['tokens']['access_token']}"}

    # permissions у /me
    me = client.get("/api/auth/me", headers=headers).json()
    assert me["permissions"]["risks"] == "manage"
    assert me["permissions"]["controls"] == "none"

    # Може створювати ризики (manage), хоча builtin-роль — reader
    response = client.post("/api/risks", json={"title": "Ризик від кастомної ролі"}, headers=headers)
    assert response.status_code == 201

    # Не може навіть читати контролі (none)
    assert client.get("/api/controls", headers=headers).status_code == 403
    # І не бачить журнал дій (none за замовчуванням для невказаних модулів)
    assert client.get("/api/audit-log", headers=headers).status_code == 403

    # Видалити роль, поки вона призначена, не можна
    assert client.delete(f"/api/roles/{role_id}", headers=admin_headers).status_code == 409


def test_api_token_auth(client, admin_headers):
    users = client.get("/api/users", headers=admin_headers).json()
    admin = next(u for u in users if u["email"] == "admin@example.com")

    response = client.post(
        "/api/api-tokens",
        json={"name": "SIEM-інтеграція", "user_id": admin["id"], "expires_days": 30},
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    token = payload["token"]
    assert token.startswith("grc_")

    # Доступ за токеном без JWT
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/risks", headers=headers)
    assert response.status_code == 200

    # last_used_at оновився
    items = client.get("/api/api-tokens", headers=admin_headers).json()
    item = next(t for t in items if t["id"] == payload["item"]["id"])
    assert item["last_used_at"] is not None

    # Відкликання — токен більше не діє
    client.delete(f"/api/api-tokens/{item['id']}", headers=admin_headers)
    assert client.get("/api/risks", headers=headers).status_code == 401

    # Невалідний токен
    bad = {"Authorization": "Bearer grc_invalid_token_xxx"}
    assert client.get("/api/risks", headers=bad).status_code == 401


def test_digest_builder(client, admin_headers):
    from app.database import SessionLocal
    from app.services.notify import build_digest

    users = client.get("/api/users", headers=admin_headers).json()
    admin = next(u for u in users if u["email"] == "admin@example.com")
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    # Прострочений ризик, призначений адміністратору
    client.post(
        "/api/risks",
        json={
            "title": "Прострочений ризик для дайджесту",
            "owner_id": admin["id"],
            "next_review_date": yesterday,
            "status": "monitored",
        },
        headers=admin_headers,
    )

    with SessionLocal() as db:
        per_user, summary = build_digest(db)

    assert "admin@example.com" in per_user
    assert any("Прострочений ризик для дайджесту" in line for line in per_user["admin@example.com"])
    assert summary and summary[0].startswith("GRC: прострочення")


def test_executor_cannot_see_audit_log(client, admin_headers):
    client.post(
        "/api/users",
        json={
            "email": "exec3@example.com",
            "full_name": "Виконавець Третій",
            "password": "Jm6&wRt9!xPv4k",
            "role": "executor",
        },
        headers=admin_headers,
    )
    auth = full_login(client, "exec3@example.com", "Jm6&wRt9!xPv4k")
    headers = {"Authorization": f"Bearer {auth['tokens']['access_token']}"}
    # Виконавець: журнал дій недоступний, ризики — читає
    assert client.get("/api/audit-log", headers=headers).status_code == 403
    assert client.get("/api/risks", headers=headers).status_code == 200
    # Адміністрування недоступне
    assert client.get("/api/roles", headers=headers).status_code == 403
