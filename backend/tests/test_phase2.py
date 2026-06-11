from tests.conftest import full_login


def _make_user(client, admin_headers, email, role):
    client.post(
        "/api/users",
        json={
            "email": email,
            "full_name": email.split("@")[0],
            "password": "Zk9#vLm2@qRt7w",
            "role": role,
        },
        headers=admin_headers,
    )
    auth = full_login(client, email, "Zk9#vLm2@qRt7w")
    return {"Authorization": f"Bearer {auth['tokens']['access_token']}"}


def test_common_password_rejected(client, admin_headers):
    response = client.post(
        "/api/users",
        json={
            "email": "weak@example.com",
            "full_name": "Слабкий Пароль",
            "password": "password12345",
            "role": "reader",
        },
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "поширений" in response.json()["detail"]


def test_nist_catalog_seeded(client, admin_headers):
    frameworks = client.get("/api/frameworks", headers=admin_headers).json()
    nist = next(f for f in frameworks if f["code"] == "nist80053")
    requirements = client.get(
        f"/api/frameworks/{nist['id']}/requirements", headers=admin_headers
    ).json()
    assert len(requirements) > 150
    assert any(r["code"] == "AC-2" for r in requirements)


def test_custom_framework_and_import(client, admin_headers):
    # Кастомний каталог для українських вимог
    response = client.post(
        "/api/frameworks",
        json={"code": "nd-tzi", "name": "НД ТЗІ (вибрані вимоги)"},
        headers=admin_headers,
    )
    assert response.status_code == 201
    framework_id = response.json()["id"]

    response = client.post(
        f"/api/frameworks/{framework_id}/requirements",
        json={"code": "НД-1.1", "title": "Тестова вимога"},
        headers=admin_headers,
    )
    assert response.status_code == 201

    # Імпорт каталогу з JSON
    response = client.post(
        "/api/frameworks/import",
        json={
            "code": "imported",
            "name": "Імпортований каталог",
            "requirements": [{"code": "X-1", "title": "Вимога 1"}],
        },
        headers=admin_headers,
    )
    assert response.status_code == 201

    # Вбудований каталог редагувати не можна
    frameworks = client.get("/api/frameworks", headers=admin_headers).json()
    iso = next(f for f in frameworks if f["code"] == "iso27001")
    response = client.post(
        f"/api/frameworks/{iso['id']}/requirements",
        json={"code": "A.99", "title": "Хак"},
        headers=admin_headers,
    )
    assert response.status_code == 403


def test_audit_lifecycle(client, admin_headers):
    frameworks = client.get("/api/frameworks", headers=admin_headers).json()
    iso = next(f for f in frameworks if f["code"] == "iso27001")

    response = client.post(
        "/api/audits",
        json={
            "title": "Внутрішній аудит ISO 27001",
            "audit_type": "internal",
            "framework_id": iso["id"],
            "scope": "Усі контролі Annex A",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    audit = response.json()
    assert audit["code"] == "AUD-001"
    audit_id = audit["id"]

    # Генерація чек-листа з фреймворка
    response = client.post(
        f"/api/audits/{audit_id}/checklist/generate", headers=admin_headers
    )
    assert response.status_code == 200
    checklist = response.json()["checklist"]
    assert len(checklist) == 93

    # Заповнення пункту
    item_id = checklist[0]["id"]
    response = client.patch(
        f"/api/audits/{audit_id}/checklist/{item_id}",
        json={"result": "non_compliant", "comment": "Політика не затверджена"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["result"] == "non_compliant"

    # Знахідка з коригувальною дією
    response = client.post(
        f"/api/audits/{audit_id}/findings",
        json={
            "title": "Відсутня затверджена політика ІБ",
            "severity": "high",
            "action_title": "Розробити та затвердити політику",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    finding = response.json()
    assert finding["code"] == "FND-001"

    # Створення ризику зі знахідки
    response = client.post(
        f"/api/audits/{audit_id}/findings/{finding['id']}/create-risk",
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["risk"]["code"].startswith("RISK-")

    # Повторне створення — конфлікт
    response = client.post(
        f"/api/audits/{audit_id}/findings/{finding['id']}/create-risk",
        headers=admin_headers,
    )
    assert response.status_code == 409


def test_policy_workflow(client, admin_headers):
    approver_headers = _make_user(client, admin_headers, "approver@example.com", "grc_manager")
    employee_headers = _make_user(client, admin_headers, "employee@example.com", "executor")

    users = client.get("/api/users", headers=admin_headers).json()
    approver = next(u for u in users if u["email"] == "approver@example.com")
    employee = next(u for u in users if u["email"] == "employee@example.com")

    # Створення політики
    response = client.post(
        "/api/policies", json={"title": "Політика інформаційної безпеки"}, headers=admin_headers
    )
    assert response.status_code == 201, response.text
    policy = response.json()
    assert policy["code"] == "POL-001"
    assert policy["status"] == "draft"
    policy_id = policy["id"]

    # Подання на погодження без тексту — відмова
    response = client.post(
        f"/api/policies/{policy_id}/submit",
        json={"approver_ids": [approver["id"]]},
        headers=admin_headers,
    )
    assert response.status_code == 400

    # Текст + подання
    client.put(
        f"/api/policies/{policy_id}/content",
        json={"content_md": "# Політика ІБ\n\nТекст політики."},
        headers=admin_headers,
    )
    response = client.post(
        f"/api/policies/{policy_id}/submit",
        json={"approver_ids": [approver["id"]]},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approval"

    # Сторонній користувач не може погоджувати
    response = client.post(
        f"/api/policies/{policy_id}/decide",
        json={"decision": "approved"},
        headers=employee_headers,
    )
    assert response.status_code == 403

    # Погодження призначеним погоджувачем
    response = client.post(
        f"/api/policies/{policy_id}/decide",
        json={"decision": "approved", "comment": "Погоджено"},
        headers=approver_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"

    # Активація та призначення ознайомлення
    response = client.post(f"/api/policies/{policy_id}/activate", headers=admin_headers)
    assert response.json()["status"] == "active"

    response = client.post(
        f"/api/policies/{policy_id}/acks",
        json={"user_ids": [employee["id"]]},
        headers=admin_headers,
    )
    assert response.status_code == 200

    # Співробітник бачить призначене ознайомлення та підтверджує
    listing = client.get("/api/policies", headers=employee_headers).json()
    mine = next(p for p in listing if p["id"] == policy_id)
    assert mine["pending_my_ack"] is True

    response = client.post(f"/api/policies/{policy_id}/acknowledge", headers=employee_headers)
    assert response.status_code == 200
    acks = response.json()["current_version"]["acks"]
    assert acks[0]["acknowledged_at"] is not None

    # Нова версія: статус «переглядається», текст успадковано, номер 2
    response = client.post(f"/api/policies/{policy_id}/new-version", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "review"
    assert body["current_version"]["number"] == 2
    assert "Текст політики" in body["current_version"]["content_md"]
    assert len(body["versions"]) == 2


def test_pdf_reports(client, admin_headers):
    frameworks = client.get("/api/frameworks", headers=admin_headers).json()
    iso = next(f for f in frameworks if f["code"] == "iso27001")
    audits = client.get("/api/audits", headers=admin_headers).json()

    endpoints = [
        "/api/reports/risk-register",
        f"/api/reports/gap-analysis/{iso['id']}",
        f"/api/reports/audit/{audits[0]['id']}",
        "/api/reports/soa",
    ]
    for url in endpoints:
        response = client.get(url, headers=admin_headers)
        assert response.status_code == 200, f"{url}: {response.text[:200]}"
        assert response.content[:4] == b"%PDF", url
