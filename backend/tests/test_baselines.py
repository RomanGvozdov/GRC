"""Інкремент 1, зріз «Baseline + категоризація ІКС» (ТЗ §5)."""

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Framework, Requirement


def _create_system(client, admin_headers, name):
    resp = client.post("/api/systems", json={"name": name}, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_seed_nd_tzi_baselines(client, admin_headers):
    baselines = client.get("/api/baselines", headers=admin_headers).json()
    by_level = {b["level"]: b for b in baselines}
    assert "nd_confidential" in by_level
    assert "nd_service" in by_level
    assert "nd_registry" in by_level
    # Три профілі НД ТЗІ над повним каталогом: 84 / 97 / 119 заходів
    assert by_level["nd_confidential"]["item_count"] == 84
    assert by_level["nd_service"]["item_count"] == 97
    assert by_level["nd_registry"]["item_count"] == 119

    detail = client.get(
        f"/api/baselines/{by_level['nd_confidential']['id']}", headers=admin_headers
    ).json()
    assert len(detail["items"]) == 84
    assert all("code" in i for i in detail["items"])


def test_create_custom_baseline_validates_catalog(client, admin_headers):
    with SessionLocal() as db:
        fw = Framework(code="bl-test", name="Baseline тест", is_custom=True)
        db.add(fw)
        db.flush()
        r1 = Requirement(framework_id=fw.id, code="BL-1", title="Захід 1", family="BL")
        r2 = Requirement(framework_id=fw.id, code="BL-2", title="Захід 2", family="BL")
        db.add_all([r1, r2])
        db.flush()
        fid, rid1, rid2 = fw.id, r1.id, r2.id
        # вимога з іншого каталогу (засіяні раніше)
        foreign_id = db.scalar(
            select(Requirement.id).where(Requirement.framework_id != fw.id).limit(1)
        )
        db.commit()

    # Вимога з чужого каталогу → 400
    bad = client.post(
        "/api/baselines",
        json={"catalog_id": fid, "name": "Поганий", "requirement_ids": [rid1, foreign_id]},
        headers=admin_headers,
    )
    assert bad.status_code == 400

    # Коректний кастомний baseline
    ok = client.post(
        "/api/baselines",
        json={"catalog_id": fid, "name": "Мій набір", "level": "custom",
              "requirement_ids": [rid1, rid2, rid1]},  # дублікат ігнорується
        headers=admin_headers,
    )
    assert ok.status_code == 201, ok.text
    body = ok.json()
    assert body["item_count"] == 2
    assert {i["code"] for i in body["items"]} == {"BL-1", "BL-2"}


def test_categorization_nist_impacts(client, admin_headers):
    system = _create_system(client, admin_headers, "ІКС для категоризації")
    resp = client.put(
        f"/api/systems/{system['id']}/categorization",
        json={"impact_confidentiality": "moderate", "impact_integrity": "high",
              "impact_availability": "low"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["overall_impact"] == "high"  # high-water-mark
    # NIST 800-53B baselines ще не засіяні (OSCAL — окремий зріз) → пропозиції немає
    assert data["suggested_baseline_id"] is None

    # Категоризація збереглась у системі
    got = client.get("/api/systems", headers=admin_headers).json()
    sys = next(s for s in got if s["id"] == system["id"])
    assert sys["impact_confidentiality"] == "moderate"
    assert sys["impact_integrity"] == "high"
    assert sys["impact_availability"] == "low"


def test_categorization_nd_profile_suggests_baseline(client, admin_headers):
    system = _create_system(client, admin_headers, "ІКС службова")
    resp = client.put(
        f"/api/systems/{system['id']}/categorization",
        json={"nd_profile_type": "service"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["profile_type"] == "service"
    assert data["suggested_baseline_id"] is not None

    suggested = client.get(
        f"/api/baselines/{data['suggested_baseline_id']}", headers=admin_headers
    ).json()
    assert suggested["level"] == "nd_service"


def test_categorization_registry_profile(client, admin_headers):
    system = _create_system(client, admin_headers, "ІКС реєстр")
    resp = client.put(
        f"/api/systems/{system['id']}/categorization",
        json={"nd_profile_type": "registry"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["profile_type"] == "registry"
    assert data["suggested_baseline_id"] is not None
    suggested = client.get(
        f"/api/baselines/{data['suggested_baseline_id']}", headers=admin_headers
    ).json()
    assert suggested["level"] == "nd_registry"
    assert suggested["item_count"] == 119


def test_categorization_requires_input(client, admin_headers):
    system = _create_system(client, admin_headers, "ІКС без даних")
    resp = client.put(
        f"/api/systems/{system['id']}/categorization", json={}, headers=admin_headers
    )
    assert resp.status_code == 400
