"""Інкремент 2, зріз «SSP» (ТЗ §6)."""

import pytest

from app.database import SessionLocal
from app.models import Baseline, BaselineItem, BaselineLevel, Framework, InformationSystem, Requirement


@pytest.fixture(scope="module")
def ssp_env(client, admin_headers):
    """Каталог 3 вимог, baseline на 2, система, профіль (через API) → база для SSP."""
    with SessionLocal() as db:
        fw = Framework(code="ssp-test", name="SSP тест", is_custom=True)
        db.add(fw)
        db.flush()
        reqs = [
            Requirement(framework_id=fw.id, code=c, title=f"Контроль {c}", family="SS")
            for c in ("SS-1", "SS-2", "SS-3")
        ]
        db.add_all(reqs)
        db.flush()
        baseline = Baseline(
            catalog_id=fw.id, name="SSP-baseline", level=BaselineLevel.CUSTOM.value
        )
        db.add(baseline)
        db.flush()
        db.add_all([
            BaselineItem(baseline_id=baseline.id, requirement_id=reqs[0].id),
            BaselineItem(baseline_id=baseline.id, requirement_id=reqs[1].id),
        ])
        system = InformationSystem(code="SYS-SSP", name="ІКС для SSP")
        db.add(system)
        db.commit()
        env = {"baseline_id": baseline.id, "system_id": system.id,
               "r1": reqs[0].id, "r2": reqs[1].id}

    profile = client.post(
        f"/api/systems/{env['system_id']}/profiles",
        json={"baseline_id": env["baseline_id"]},
        headers=admin_headers,
    ).json()
    env["profile_id"] = profile["id"]
    return env


def _gen_ssp(client, admin_headers, env):
    resp = client.post(
        f"/api/systems/{env['system_id']}/ssp",
        json={"profile_id": env["profile_id"], "system_description": "Тестова ІКС"},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_generate_ssp_from_profile(client, admin_headers, ssp_env):
    ssp = _gen_ssp(client, admin_headers, ssp_env)
    assert ssp["version"] == 1 and ssp["status"] == "draft"
    assert ssp["control_count"] == 2  # включені контролі профілю (SS-1, SS-2)
    assert ssp["implemented_count"] == 0
    assert all(c["implementation_status"] == "not_implemented" for c in ssp["controls"])


def test_ssp_wrong_system_rejected(client, admin_headers, ssp_env):
    other = client.post(
        "/api/systems", json={"name": "Інша ІКС для SSP"}, headers=admin_headers
    ).json()
    resp = client.post(
        f"/api/systems/{other['id']}/ssp",
        json={"profile_id": ssp_env["profile_id"]},
        headers=admin_headers,
    )
    assert resp.status_code == 400


def test_edit_control_and_approve_and_version(client, admin_headers, ssp_env):
    ssp = _gen_ssp(client, admin_headers, ssp_env)
    sid = ssp["id"]

    # Заповнити наратив + статус
    r = client.put(
        f"/api/ssp/{sid}/controls/{ssp_env['r1']}",
        json={"implementation_status": "implemented", "narrative": "Реалізовано через AD"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["implemented_count"] == 1
    c1 = next(c for c in body["controls"] if c["requirement"]["id"] == ssp_env["r1"])
    assert c1["narrative"] == "Реалізовано через AD"

    # Затвердити → редагування 409
    assert client.post(f"/api/ssp/{sid}/approve", headers=admin_headers).status_code == 200
    r = client.put(
        f"/api/ssp/{sid}/controls/{ssp_env['r1']}",
        json={"narrative": "пізно"}, headers=admin_headers,
    )
    assert r.status_code == 409

    # Нова версія — клон наративів, стара superseded
    nv = client.post(f"/api/ssp/{sid}/new-version", headers=admin_headers)
    assert nv.status_code == 201, nv.text
    new = nv.json()
    assert new["version"] == 2 and new["status"] == "draft"
    c1 = next(c for c in new["controls"] if c["requirement"]["id"] == ssp_env["r1"])
    assert c1["narrative"] == "Реалізовано через AD"  # наратив склонувався
    old = client.get(f"/api/ssp/{sid}", headers=admin_headers).json()
    assert old["status"] == "superseded"


def test_ssp_oscal_export(client, admin_headers, ssp_env):
    ssp = _gen_ssp(client, admin_headers, ssp_env)
    client.put(
        f"/api/ssp/{ssp['id']}/controls/{ssp_env['r1']}",
        json={"implementation_status": "implemented", "narrative": "Налаштовано"},
        headers=admin_headers,
    )
    resp = client.get(f"/api/ssp/{ssp['id']}/oscal", headers=admin_headers)
    assert resp.status_code == 200
    doc = resp.json()
    plan = doc["system-security-plan"]
    assert plan["metadata"]["oscal-version"] == "1.1.2"
    assert plan["system-characteristics"]["system-name"] == "ІКС для SSP"
    impl = plan["control-implementation"]["implemented-requirements"]
    ids = {ir["control-id"] for ir in impl}
    assert ids == {"ss-1", "ss-2"}  # коди в нижньому регістрі
    ss1 = next(ir for ir in impl if ir["control-id"] == "ss-1")
    assert ss1["props"][0]["value"] == "implemented"


def test_ssp_xlsx_export(client, admin_headers, ssp_env):
    ssp = _gen_ssp(client, admin_headers, ssp_env)
    resp = client.get(f"/api/ssp/{ssp['id']}/export?fmt=xlsx", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.content[:2] == b"PK"  # xlsx = zip
