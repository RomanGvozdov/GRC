"""Інкремент 1, зріз «Profile + tailoring» (ТЗ §5)."""

import pytest

from app.database import SessionLocal
from app.models import (
    Baseline,
    BaselineItem,
    BaselineLevel,
    ControlParameter,
    Framework,
    InformationSystem,
    Requirement,
)


@pytest.fixture(scope="module")
def env():
    """Каталог із 3 вимог (одна з ODP-параметром), baseline на 2 з них, система."""
    with SessionLocal() as db:
        fw = Framework(code="prof-test", name="Профіль тест", is_custom=True)
        db.add(fw)
        db.flush()
        r1 = Requirement(framework_id=fw.id, code="PR-1", title="Контроль 1", family="PR")
        r2 = Requirement(framework_id=fw.id, code="PR-2", title="Контроль 2", family="PR")
        r3 = Requirement(framework_id=fw.id, code="PR-3", title="Контроль 3", family="PR")
        db.add_all([r1, r2, r3])
        db.flush()
        param = ControlParameter(
            requirement_id=r1.id, key="pr-1_odp.01", label="Період",
            default_value="30 днів",
        )
        db.add(param)
        baseline = Baseline(
            catalog_id=fw.id, name="Профіль-baseline", level=BaselineLevel.CUSTOM.value
        )
        db.add(baseline)
        db.flush()
        db.add_all([
            BaselineItem(baseline_id=baseline.id, requirement_id=r1.id),
            BaselineItem(baseline_id=baseline.id, requirement_id=r2.id),
        ])
        system = InformationSystem(code="SYS-PR", name="ІКС для профілів")
        db.add(system)
        db.commit()
        return {
            "catalog_id": fw.id, "baseline_id": baseline.id, "system_id": system.id,
            "r1": r1.id, "r2": r2.id, "r3": r3.id, "param_id": param.id,
        }


def _generate(client, admin_headers, env):
    resp = client.post(
        f"/api/systems/{env['system_id']}/profiles",
        json={"baseline_id": env["baseline_id"]},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_generate_profile_from_baseline(client, admin_headers, env):
    profile = _generate(client, admin_headers, env)
    assert profile["version"] == 1
    assert profile["status"] == "draft"
    assert profile["control_count"] == 2  # PR-1, PR-2 (PR-3 поза baseline)
    assert all(c["origin"] == "baseline" and c["included"] for c in profile["controls"])
    codes = {c["requirement"]["code"] for c in profile["controls"]}
    assert codes == {"PR-1", "PR-2"}


def test_tailoring_requires_justification(client, admin_headers, env):
    profile = _generate(client, admin_headers, env)
    pid = profile["id"]
    # Без обґрунтування — 422 (поле обов'язкове)
    r = client.post(
        f"/api/profiles/{pid}/tailoring",
        json={"action": "remove", "requirement_id": env["r1"]},
        headers=admin_headers,
    )
    assert r.status_code == 422
    # Порожнє/пробільне — теж 422
    r = client.post(
        f"/api/profiles/{pid}/tailoring",
        json={"action": "remove", "requirement_id": env["r1"], "justification": "   "},
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_tailoring_remove_and_add(client, admin_headers, env):
    profile = _generate(client, admin_headers, env)
    pid = profile["id"]

    # Вилучити PR-1 з обґрунтуванням
    r = client.post(
        f"/api/profiles/{pid}/tailoring",
        json={"action": "remove", "requirement_id": env["r1"],
              "justification": "Не застосовно до цієї ІКС"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["control_count"] == 1
    pr1 = next(c for c in body["controls"] if c["requirement"]["code"] == "PR-1")
    assert pr1["included"] is False

    # Додати PR-3 (поза baseline)
    r = client.post(
        f"/api/profiles/{pid}/tailoring",
        json={"action": "add", "requirement_id": env["r3"],
              "justification": "Додатковий захід за результатами оцінки ризику"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["control_count"] == 2  # PR-2 + PR-3
    pr3 = next(c for c in body["controls"] if c["requirement"]["code"] == "PR-3")
    assert pr3["origin"] == "added" and pr3["included"]
    assert len(body["decisions"]) == 2

    # Резолвлене подання: лише включені (PR-2, PR-3), без PR-1
    resolved = client.get(f"/api/profiles/{pid}/resolved", headers=admin_headers).json()
    codes = {c["code"] for c in resolved["controls"]}
    assert codes == {"PR-2", "PR-3"}


def test_add_from_wrong_catalog_rejected(client, admin_headers, env):
    profile = _generate(client, admin_headers, env)
    pid = profile["id"]
    with SessionLocal() as db:
        from sqlalchemy import select
        foreign_id = db.scalar(
            select(Requirement.id).where(Requirement.framework_id != env["catalog_id"]).limit(1)
        )
    r = client.post(
        f"/api/profiles/{pid}/tailoring",
        json={"action": "add", "requirement_id": foreign_id,
              "justification": "спроба додати чужий контроль"},
        headers=admin_headers,
    )
    assert r.status_code == 400


def test_modify_param_resolved(client, admin_headers, env):
    profile = _generate(client, admin_headers, env)
    pid = profile["id"]

    # До зміни — резолвиться default параметра
    resolved = client.get(f"/api/profiles/{pid}/resolved", headers=admin_headers).json()
    pr1 = next(c for c in resolved["controls"] if c["code"] == "PR-1")
    assert pr1["parameters"][0]["value"] == "30 днів"

    # Задати значення ODP
    r = client.post(
        f"/api/profiles/{pid}/tailoring",
        json={"action": "modify_param", "parameter_id": env["param_id"], "value": "7 днів",
              "justification": "Жорсткіша вимога для цієї ІКС"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text

    resolved = client.get(f"/api/profiles/{pid}/resolved", headers=admin_headers).json()
    pr1 = next(c for c in resolved["controls"] if c["code"] == "PR-1")
    assert pr1["parameters"][0]["value"] == "7 днів"  # значення профілю перекрило default


def test_approve_makes_immutable_and_new_version(client, admin_headers, env):
    profile = _generate(client, admin_headers, env)
    pid = profile["id"]

    approve = client.post(f"/api/profiles/{pid}/approve", headers=admin_headers)
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "approved"

    # Tailoring на затвердженому — 409
    r = client.post(
        f"/api/profiles/{pid}/tailoring",
        json={"action": "remove", "requirement_id": env["r1"], "justification": "пізно"},
        headers=admin_headers,
    )
    assert r.status_code == 409

    # Нова версія — чернетка з копією контролів; стара стає superseded
    nv = client.post(f"/api/profiles/{pid}/new-version", headers=admin_headers)
    assert nv.status_code == 201, nv.text
    new = nv.json()
    assert new["version"] == 2
    assert new["status"] == "draft"
    assert new["parent_profile_id"] == pid
    assert new["control_count"] == 2

    old = client.get(f"/api/profiles/{pid}", headers=admin_headers).json()
    assert old["status"] == "superseded"

    # На новій версії tailoring знову дозволено
    r = client.post(
        f"/api/profiles/{new['id']}/tailoring",
        json={"action": "remove", "requirement_id": env["r1"], "justification": "у новій версії"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text


def test_apply_overlay(client, admin_headers, env):
    profile = _generate(client, admin_headers, env)
    pid = profile["id"]

    overlay = client.post(
        "/api/overlays",
        json={"catalog_id": env["catalog_id"], "name": "Тест-overlay",
              "items": [{"requirement_id": env["r3"], "action": "add"},
                        {"requirement_id": env["r1"], "action": "remove"}]},
        headers=admin_headers,
    )
    assert overlay.status_code == 201, overlay.text
    oid = overlay.json()["id"]

    r = client.post(
        f"/api/profiles/{pid}/apply-overlay/{oid}",
        json={"justification": "Стандартний набір для службових ІКС"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # PR-1 вилучено, PR-3 додано → лишаються PR-2, PR-3
    included = {c["requirement"]["code"] for c in body["controls"] if c["included"]}
    assert included == {"PR-2", "PR-3"}


def test_list_profiles_for_system(client, admin_headers, env):
    _generate(client, admin_headers, env)
    resp = client.get(f"/api/systems/{env['system_id']}/profiles", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
