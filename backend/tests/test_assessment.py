"""Інкремент 3: оцінювання контролів (800-53A, ТЗ §7)."""

import pytest

from app.database import SessionLocal
from app.models import Baseline, BaselineItem, BaselineLevel, Framework, Requirement


@pytest.fixture(scope="module")
def assess_env(client, admin_headers):
    with SessionLocal() as db:
        fw = Framework(code="assess-test", name="Assess тест", is_custom=True)
        db.add(fw)
        db.flush()
        reqs = [
            Requirement(framework_id=fw.id, code=c, title=f"Контроль {c}", family="AS")
            for c in ("AS-1", "AS-2")
        ]
        db.add_all(reqs)
        db.flush()
        bl = Baseline(catalog_id=fw.id, name="Assess-baseline", level=BaselineLevel.CUSTOM.value)
        db.add(bl)
        db.flush()
        db.add_all([BaselineItem(baseline_id=bl.id, requirement_id=r.id) for r in reqs])
        db.commit()
        env = {"baseline_id": bl.id, "r1": reqs[0].id, "r2": reqs[1].id}

    sys = client.post(
        "/api/systems", json={"name": "ІКС оцінювання"}, headers=admin_headers
    ).json()
    env["system_id"] = sys["id"]
    env["profile_id"] = client.post(
        f"/api/systems/{sys['id']}/profiles",
        json={"baseline_id": env["baseline_id"]}, headers=admin_headers,
    ).json()["id"]
    return env


def test_generate_and_assess(client, admin_headers, assess_env):
    resp = client.post(
        f"/api/systems/{assess_env['system_id']}/assessments",
        json={"profile_id": assess_env["profile_id"]},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    a = resp.json()
    assert a["total"] == 2 and a["not_assessed"] == 2 and a["status"] == "in_progress"
    aid = a["id"]

    # Оцінити: AS-1 satisfied, AS-2 other-than-satisfied
    r = client.put(
        f"/api/assessments/{aid}/results/{assess_env['r1']}",
        json={"result": "satisfied", "notes": "Перевірено"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    r = client.put(
        f"/api/assessments/{aid}/results/{assess_env['r2']}",
        json={"result": "other_than_satisfied", "notes": "Не виконано вимогу b"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["satisfied"] == 1 and body["other_than_satisfied"] == 1

    # Завершити
    r = client.patch(f"/api/assessments/{aid}", json={"status": "completed"},
                     headers=admin_headers)
    assert r.status_code == 200 and r.json()["status"] == "completed"

    # other-than-satisfied → POA&M
    r = client.post(f"/api/assessments/{aid}/to-poam", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 1
    assert r.json()["items"][0]["source"] == "from_finding"

    # Повторно — дубль пропущено
    r2 = client.post(f"/api/assessments/{aid}/to-poam", headers=admin_headers).json()
    assert r2["created"] == 0 and r2["skipped"] == 1


def test_assessment_wrong_system(client, admin_headers, assess_env):
    other = client.post(
        "/api/systems", json={"name": "Інша ІКС оцінювання"}, headers=admin_headers
    ).json()
    resp = client.post(
        f"/api/systems/{other['id']}/assessments",
        json={"profile_id": assess_env["profile_id"]},
        headers=admin_headers,
    )
    assert resp.status_code == 400
