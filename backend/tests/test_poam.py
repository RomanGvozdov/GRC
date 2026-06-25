"""Інкремент 2, зріз «POA&M» (ТЗ §6)."""

import pytest

from app.database import SessionLocal
from app.models import Baseline, BaselineItem, BaselineLevel, Framework, Requirement


@pytest.fixture(scope="module")
def poam_cat():
    """Каталог 2 вимог + baseline на обидві (для генерації профілів у тестах)."""
    with SessionLocal() as db:
        fw = Framework(code="poam-test", name="POAM тест", is_custom=True)
        db.add(fw)
        db.flush()
        reqs = [
            Requirement(framework_id=fw.id, code=c, title=f"Контроль {c}", family="PO")
            for c in ("PO-1", "PO-2")
        ]
        db.add_all(reqs)
        db.flush()
        baseline = Baseline(catalog_id=fw.id, name="POAM-baseline",
                            level=BaselineLevel.CUSTOM.value)
        db.add(baseline)
        db.flush()
        db.add_all([BaselineItem(baseline_id=baseline.id, requirement_id=r.id) for r in reqs])
        db.commit()
        return {"baseline_id": baseline.id}


def _system(client, admin_headers, name):
    return client.post("/api/systems", json={"name": name}, headers=admin_headers).json()


def test_manual_poam_and_milestones(client, admin_headers):
    sys = _system(client, admin_headers, "ІКС POA&M ручна")
    sid = sys["id"]
    r = client.post(
        f"/api/systems/{sid}/poam",
        json={"title": "Слабкий пароль адміна", "weakness": "Політика паролів не застосована",
              "severity": "high"},
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["status"] == "open" and item["source"] == "manual"
    assert item["severity"] == "high"
    iid = item["id"]

    # Контрольна точка
    r = client.post(
        f"/api/poam/{iid}/milestones",
        json={"title": "Увімкнути парольну політику", "due_date": "2026-08-01"},
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["milestone_count"] == 1
    mid = r.json()["milestones"][0]["id"]

    # Виконати точку
    r = client.patch(
        f"/api/poam/milestones/{mid}", json={"completed": True}, headers=admin_headers
    )
    assert r.status_code == 200
    assert r.json()["milestone_done"] == 1

    # Оновити статус пункту
    r = client.patch(f"/api/poam/{iid}", json={"status": "completed"}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "completed"

    # У списку системи
    items = client.get(f"/api/systems/{sid}/poam", headers=admin_headers).json()
    assert any(i["id"] == iid for i in items)


def test_poam_from_profile_gaps(client, admin_headers, poam_cat):
    sys = _system(client, admin_headers, "ІКС POA&M прогалини")
    sid = sys["id"]
    profile = client.post(
        f"/api/systems/{sid}/profiles",
        json={"baseline_id": poam_cat["baseline_id"]},
        headers=admin_headers,
    ).json()

    # Контролі профілю не мають впроваджень → not_covered → пункти створюються
    r = client.post(
        f"/api/systems/{sid}/poam/from-profile/{profile['id']}", headers=admin_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 2 and body["skipped"] == 0
    assert all(i["source"] == "from_gap" and i["status"] == "open" for i in body["items"])

    # Повторний запуск — усе пропущено (дедуплікація за відкритими пунктами)
    r2 = client.post(
        f"/api/systems/{sid}/poam/from-profile/{profile['id']}", headers=admin_headers
    ).json()
    assert r2["created"] == 0 and r2["skipped"] == 2


def test_poam_exports(client, admin_headers, poam_cat):
    sys = _system(client, admin_headers, "ІКС POA&M експорт")
    sid = sys["id"]
    client.post(
        f"/api/systems/{sid}/poam",
        json={"title": "Недолік для експорту", "severity": "medium"},
        headers=admin_headers,
    )
    # OSCAL
    resp = client.get(f"/api/systems/{sid}/poam/oscal", headers=admin_headers)
    assert resp.status_code == 200
    doc = resp.json()
    plan = doc["plan-of-action-and-milestones"]
    assert plan["metadata"]["oscal-version"] == "1.1.2"
    assert len(plan["poam-items"]) == 1
    assert plan["poam-items"][0]["title"] == "Недолік для експорту"

    # XLSX
    resp = client.get(f"/api/systems/{sid}/poam/export?fmt=xlsx", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.content[:2] == b"PK"
