def test_risk_lifecycle(client, admin_headers):
    # Створення
    response = client.post(
        "/api/risks",
        json={"title": "Витік даних через фішинг", "status": "identified"},
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    risk = response.json()
    assert risk["code"] == "RISK-001"
    risk_id = risk["id"]

    # Оцінка (притаманний ризик) — статус стає "оцінений", рахується score
    response = client.post(
        f"/api/risks/{risk_id}/assessments",
        json={"kind": "inherent", "likelihood": 4, "impact": 5},
        headers=admin_headers,
    )
    assert response.status_code == 200
    risk = response.json()
    assert risk["inherent_score"] == 20
    assert risk["status"] == "assessed"

    response = client.post(
        f"/api/risks/{risk_id}/assessments",
        json={"kind": "residual", "likelihood": 2, "impact": 3},
        headers=admin_headers,
    )
    risk = response.json()
    assert risk["residual_score"] == 6
    assert risk["residual_level"] == "medium"
    assert len(risk["assessments"]) == 2

    # План обробки
    response = client.post(
        f"/api/risks/{risk_id}/actions",
        json={"title": "Впровадити навчання з фішингу", "status": "open"},
        headers=admin_headers,
    )
    assert response.status_code == 201


def test_high_risk_acceptance_requires_comment(client, admin_headers):
    response = client.post(
        "/api/risks", json={"title": "Критичний ризик"}, headers=admin_headers
    )
    risk_id = response.json()["id"]
    client.post(
        f"/api/risks/{risk_id}/assessments",
        json={"kind": "residual", "likelihood": 4, "impact": 4},
        headers=admin_headers,
    )

    # Прийняття без коментаря — відмова (рівень 16 >= порога 10)
    response = client.put(
        f"/api/risks/{risk_id}",
        json={"title": "Критичний ризик", "treatment_strategy": "accept"},
        headers=admin_headers,
    )
    assert response.status_code == 400

    # З коментарем — успіх, фіксується хто затвердив
    response = client.put(
        f"/api/risks/{risk_id}",
        json={
            "title": "Критичний ризик",
            "treatment_strategy": "accept",
            "acceptance_comment": "Бізнес приймає ризик до кінця кварталу",
        },
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["accepted_by"]["email"] == "admin@example.com"


def test_iso_catalog_seeded(client, admin_headers):
    response = client.get("/api/frameworks", headers=admin_headers)
    assert response.status_code == 200
    frameworks = response.json()
    iso = next(f for f in frameworks if f["code"] == "iso27001")

    response = client.get(
        f"/api/frameworks/{iso['id']}/requirements", headers=admin_headers
    )
    requirements = response.json()
    assert len(requirements) == 93


def test_control_mapping_and_gap_analysis(client, admin_headers):
    frameworks = client.get("/api/frameworks", headers=admin_headers).json()
    iso = next(f for f in frameworks if f["code"] == "iso27001")
    requirements = client.get(
        f"/api/frameworks/{iso['id']}/requirements", headers=admin_headers
    ).json()
    req_a51 = next(r for r in requirements if r["code"] == "A.5.1")

    # Статус "не застосовно" без обґрунтування — відмова
    response = client.post(
        "/api/controls",
        json={"name": "Тест NA", "implementation_status": "not_applicable"},
        headers=admin_headers,
    )
    assert response.status_code == 400

    # Створення контролю з мапінгом на A.5.1
    response = client.post(
        "/api/controls",
        json={
            "name": "Затверджена політика ІБ",
            "control_type": "preventive",
            "implementation_status": "implemented",
            "requirement_ids": [req_a51["id"]],
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    control = response.json()
    assert control["code"] == "CTRL-001"
    assert control["requirements"][0]["code"] == "A.5.1"

    # Gap-аналіз: A.5.1 покрита, решта — ні
    response = client.get(
        f"/api/frameworks/{iso['id']}/gap-analysis", headers=admin_headers
    )
    gap = response.json()
    assert gap["covered"] == 1
    assert gap["not_covered"] == 92
    row = next(r for r in gap["requirements"] if r["requirement"]["code"] == "A.5.1")
    assert row["coverage"] == "covered"


def test_dashboard_and_exports(client, admin_headers):
    response = client.get("/api/dashboard", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["risks_total"] >= 2
    assert data["frameworks"]

    for fmt in ("xlsx", "csv"):
        response = client.get(f"/api/exports/risks?fmt={fmt}", headers=admin_headers)
        assert response.status_code == 200
        response = client.get(f"/api/exports/controls?fmt={fmt}", headers=admin_headers)
        assert response.status_code == 200


def test_audit_log_records_actions(client, admin_headers):
    response = client.get("/api/audit-log", headers=admin_headers)
    assert response.status_code == 200
    actions = {entry["action"] for entry in response.json()}
    assert "create" in actions
    assert "assess" in actions
