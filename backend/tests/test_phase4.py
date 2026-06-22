import io

from openpyxl import Workbook


def _make_system(client, headers, name):
    response = client.post("/api/systems", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_systems_and_implementation_matrix(client, admin_headers):
    sys_a = _make_system(client, admin_headers, "Корпоративна мережа")
    sys_b = _make_system(client, admin_headers, "Вебпортал")

    # Контроль зі стартовим впровадженням «вся організація»
    response = client.post(
        "/api/controls", json={"name": "Антивірусний захист"}, headers=admin_headers
    )
    control = response.json()
    control_id = control["id"]
    org_impl = control["implementations"][0]
    assert org_impl["system"] is None

    # Впровадження для системи А (впроваджено) і Б (частково)
    client.post(
        f"/api/controls/{control_id}/implementations",
        json={"system_id": sys_a["id"], "implementation_status": "implemented"},
        headers=admin_headers,
    )
    response = client.post(
        f"/api/controls/{control_id}/implementations",
        json={"system_id": sys_b["id"], "implementation_status": "partial"},
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    control = response.json()
    assert len(control["implementations"]) == 3
    # Найгірший серед (not_implemented, implemented, partial) = not_implemented
    assert control["aggregate_status"] == "not_implemented"

    # Дубль впровадження для тієї ж системи — конфлікт
    response = client.post(
        f"/api/controls/{control_id}/implementations",
        json={"system_id": sys_a["id"]},
        headers=admin_headers,
    )
    assert response.status_code == 409

    # Видалити систему з впровадженнями не можна
    response = client.delete(f"/api/systems/{sys_a['id']}", headers=admin_headers)
    assert response.status_code == 409


def test_gap_analysis_per_system(client, admin_headers):
    systems = client.get("/api/systems", headers=admin_headers).json()
    sys_a = next(s for s in systems if s["name"] == "Корпоративна мережа")
    sys_b = next(s for s in systems if s["name"] == "Вебпортал")

    frameworks = client.get("/api/frameworks", headers=admin_headers).json()
    iso = next(f for f in frameworks if f["code"] == "iso27001")
    requirements = client.get(
        f"/api/frameworks/{iso['id']}/requirements", headers=admin_headers
    ).json()
    req = next(r for r in requirements if r["code"] == "A.8.7")  # Захист від шкідливого ПЗ

    # Прив'язуємо контроль «Антивірусний захист» до A.8.7
    controls = client.get("/api/controls", headers=admin_headers).json()
    control = next(c for c in controls if c["name"] == "Антивірусний захист")
    client.put(
        f"/api/controls/{control['id']}",
        json={"name": control["name"], "requirement_ids": [req["id"]]},
        headers=admin_headers,
    )

    def coverage_of(system_id=None):
        url = f"/api/frameworks/{iso['id']}/gap-analysis"
        if system_id:
            url += f"?system_id={system_id}"
        gap = client.get(url, headers=admin_headers).json()
        row = next(r for r in gap["requirements"] if r["requirement"]["code"] == "A.8.7")
        return row["coverage"]

    # Система А: специфічне впровадження «впроваджено» → покрито
    assert coverage_of(sys_a["id"]) == "covered"
    # Система Б: «частково»
    assert coverage_of(sys_b["id"]) == "partial"
    # Вся організація: найгірший статус (not_implemented в org-wide) → не покрито
    assert coverage_of(None) == "not_covered"


def test_system_filter_on_risks(client, admin_headers):
    systems = client.get("/api/systems", headers=admin_headers).json()
    sys_a = next(s for s in systems if s["name"] == "Корпоративна мережа")
    sys_b = next(s for s in systems if s["name"] == "Вебпортал")

    response = client.post(
        "/api/risks",
        json={"title": "Ризик лише вебпорталу", "system_ids": [sys_b["id"]]},
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["systems"][0]["name"] == "Вебпортал"

    # У контексті системи А ризик вебпорталу не видно, але загальні — видно
    in_a = client.get(f"/api/risks?system_id={sys_a['id']}", headers=admin_headers).json()
    assert all(r["title"] != "Ризик лише вебпорталу" for r in in_a)
    in_b = client.get(f"/api/risks?system_id={sys_b['id']}", headers=admin_headers).json()
    assert any(r["title"] == "Ризик лише вебпорталу" for r in in_b)


def test_my_tasks(client, admin_headers):
    users = client.get("/api/users", headers=admin_headers).json()
    admin = next(u for u in users if u["email"] == "admin@example.com")

    response = client.post("/api/risks", json={"title": "Ризик для задач"}, headers=admin_headers)
    risk_id = response.json()["id"]
    client.post(
        f"/api/risks/{risk_id}/actions",
        json={"title": "Моя дія з обробки", "assignee_id": admin["id"]},
        headers=admin_headers,
    )

    tasks = client.get("/api/my-tasks", headers=admin_headers).json()
    assert any(
        t["kind"] == "treatment_action" and t["title"] == "Моя дія з обробки" for t in tasks
    )
    # Прострочений ризик з test_phase3 теж має бути тут
    assert any(t["kind"] == "risk_review" and t["overdue"] for t in tasks)


def _xlsx(headers, rows) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def test_import_risks(client, admin_headers):
    from app.api.imports import RISK_HEADERS

    content = _xlsx(RISK_HEADERS, [
        ["Імпортований ризик 1", "Опис", "Нова категорія з імпорту", "Ідентифікований",
         "admin@example.com", "Нова ІКС з імпорту", 4, 4, 2, 2, "Зменшити",
         "2026-12-31", "", "", ""],
        ["Поганий рядок", "", "", "Неіснуючий статус", "", "", 9, "", "", "", "", "", "", "", ""],
    ])
    files = {"file": ("risks.xlsx", content,
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}

    # Dry-run: 1 валідний, 1 з помилками, нічого не створено
    report = client.post(
        "/api/imports/risks?dry_run=true", files=files, headers=admin_headers
    ).json()
    assert report["valid_rows"] == 1
    assert len(report["errors"]) == 1
    assert report["created"] == 0

    # Реальний імпорт
    files = {"file": ("risks.xlsx", content,
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    report = client.post(
        "/api/imports/risks?dry_run=false", files=files, headers=admin_headers
    ).json()
    assert report["created"] == 1

    risks = client.get("/api/risks?search=Імпортований", headers=admin_headers).json()
    assert len(risks) == 1
    imported = risks[0]
    assert imported["category"]["name"] == "Нова категорія з імпорту"
    assert imported["systems"][0]["name"] == "Нова ІКС з імпорту"
    assert imported["inherent_score"] == 16


def test_import_controls(client, admin_headers):
    from app.api.imports import CONTROL_HEADERS

    content = _xlsx(CONTROL_HEADERS, [
        ["Імпортований контроль", "Опис", "Превентивний", "admin@example.com",
         "A.8.13", "Корпоративна мережа, Вебпортал", "Впроваджено", "", "2026-09-01"],
    ])
    files = {"file": ("controls.xlsx", content,
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    report = client.post(
        "/api/imports/controls?dry_run=false", files=files, headers=admin_headers
    ).json()
    assert report["created"] == 1, report

    controls = client.get("/api/controls?search=Імпортований", headers=admin_headers).json()
    control = controls[0]
    assert control["aggregate_status"] == "implemented"
    assert len(control["systems"]) == 2

    detail = client.get(f"/api/controls/{control['id']}", headers=admin_headers).json()
    assert len(detail["implementations"]) == 2
    assert detail["requirements"][0]["code"] == "A.8.13"


def test_import_template_download(client, admin_headers):
    response = client.get("/api/imports/template/risks", headers=admin_headers)
    assert response.status_code == 200
    assert response.content[:2] == b"PK"  # xlsx = zip


def test_base_profiles_nd_tzi(client, admin_headers):
    # Системи з типами базових профілів
    response = client.post(
        "/api/systems",
        json={"name": "АС конфіденційної інформації", "profile_type": "confidential"},
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    sys_conf = response.json()
    assert sys_conf["profile_type"] == "confidential"

    response = client.post(
        "/api/systems",
        json={"name": "АС службової інформації", "profile_type": "service"},
        headers=admin_headers,
    )
    sys_serv = response.json()

    # Каталог НД ТЗІ з вимогами, розподіленими за профілями
    response = client.post(
        "/api/frameworks/import",
        json={
            "code": "nd-tzi-test-profiles",
            "name": "НД ТЗІ (тест профілів)",
            "requirements": [
                {"code": "Т-1", "title": "Спільна вимога", "profiles": []},
                {"code": "Т-2", "title": "Лише конфіденційна", "profiles": ["confidential"]},
                {"code": "Т-3", "title": "Лише службова", "profiles": ["service"]},
            ],
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    framework_id = response.json()["id"]

    # Невідомий профіль — відмова
    response = client.post(
        f"/api/frameworks/{framework_id}/requirements",
        json={"code": "Т-X", "title": "Хибна", "profiles": ["secret"]},
        headers=admin_headers,
    )
    assert response.status_code == 400

    # profiles повертаються у вимогах
    requirements = client.get(
        f"/api/frameworks/{framework_id}/requirements", headers=admin_headers
    ).json()
    t2 = next(r for r in requirements if r["code"] == "Т-2")
    assert t2["profiles"] == ["confidential"]

    def gap_codes(system_id=None):
        url = f"/api/frameworks/{framework_id}/gap-analysis"
        if system_id:
            url += f"?system_id={system_id}"
        gap = client.get(url, headers=admin_headers).json()
        return {r["requirement"]["code"] for r in gap["requirements"]}, gap["total"]

    # Вся організація: всі 3 вимоги
    codes, total = gap_codes()
    assert codes == {"Т-1", "Т-2", "Т-3"} and total == 3
    # Конфіденційна система: спільна + конфіденційна
    codes, total = gap_codes(sys_conf["id"])
    assert codes == {"Т-1", "Т-2"} and total == 2
    # Службова система: спільна + службова
    codes, total = gap_codes(sys_serv["id"])
    assert codes == {"Т-1", "Т-3"} and total == 2


def test_nd_tzi_seed_catalog(client, admin_headers):
    """Об'єднаний базовий профіль НД ТЗІ 3.6-006-24: 98 заходів, два профілі."""
    frameworks = client.get("/api/frameworks", headers=admin_headers).json()
    nd = next((f for f in frameworks if f["code"] == "nd-tzi-3-6-006-24"), None)
    assert nd is not None, "Каталог НД ТЗІ не засіявся"
    assert nd["is_custom"] is True  # редагований, щоб додавати посилені заходи

    # Без контексту системи — усі 98 заходів
    reqs = client.get(
        f"/api/frameworks/{nd['id']}/requirements", headers=admin_headers
    ).json()
    assert len(reqs) == 98
    by_code = {r["code"]: r for r in reqs}
    assert {"AC-2", "AU-3", "IR-8", "SC-13", "PL-2"} <= set(by_code)
    # Захід лише для конфіденційної та лише для службової
    assert by_code["AC-6(10)"]["profiles"] == ["confidential"]
    assert by_code["SR-2"]["profiles"] == ["service"]
    # AC-2 належить обом профілям
    assert set(by_code["AC-2"]["profiles"]) == {"confidential", "service"}

    # Системи з різними профілями
    sys_conf = client.post(
        "/api/systems",
        json={"name": "АС конфіденційна НД ТЗІ", "profile_type": "confidential"},
        headers=admin_headers,
    ).json()
    sys_serv = client.post(
        "/api/systems",
        json={"name": "АС службова НД ТЗІ", "profile_type": "service"},
        headers=admin_headers,
    ).json()

    conf_reqs = client.get(
        f"/api/frameworks/{nd['id']}/requirements?system_id={sys_conf['id']}",
        headers=admin_headers,
    ).json()
    serv_reqs = client.get(
        f"/api/frameworks/{nd['id']}/requirements?system_id={sys_serv['id']}",
        headers=admin_headers,
    ).json()
    assert len(conf_reqs) == 84
    assert len(serv_reqs) == 97

    # AC-2 має РІЗНИЙ текст під профіль (службова — суворіша)
    ac2_conf = next(r for r in conf_reqs if r["code"] == "AC-2")["description"]
    ac2_serv = next(r for r in serv_reqs if r["code"] == "AC-2")["description"]
    assert ac2_conf != ac2_serv
    assert len(ac2_serv) > len(ac2_conf)

    # Gap-аналіз поважає профіль системи
    def gap_total(system_id):
        return client.get(
            f"/api/frameworks/{nd['id']}/gap-analysis?system_id={system_id}",
            headers=admin_headers,
        ).json()["total"]

    assert gap_total(sys_conf["id"]) == 84
    assert gap_total(sys_serv["id"]) == 97


def test_nd_tzi_full_catalog_seed(client, admin_headers):
    """Повний каталог заходів НД ТЗІ — усі заходи з усіх 20 класів."""
    frameworks = client.get("/api/frameworks", headers=admin_headers).json()
    full = next((f for f in frameworks if f["code"] == "nd-tzi-3-6-006-24-full"), None)
    assert full is not None, "Повний каталог не засіявся"

    reqs = client.get(
        f"/api/frameworks/{full['id']}/requirements", headers=admin_headers
    ).json()
    assert len(reqs) > 300
    codes = {r["code"] for r in reqs}
    # заходи, яких немає в базових профілях, теж присутні
    assert {"AC-16", "AC-21", "AU-10", "SR-7", "PM-1", "PT-1"} <= codes
    # 20 класів за префіксом коду
    families = {c.split("-")[0] for c in codes}
    assert len(families) == 20
