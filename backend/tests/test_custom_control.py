"""Додавання власного заходу захисту в оформленні базових профілів."""

import pytest

from app.database import SessionLocal
from app.models import Baseline, BaselineItem, BaselineLevel, Framework, InformationSystem, Requirement


@pytest.fixture(scope="module")
def cc_env(client, admin_headers):
    with SessionLocal() as db:
        fw = Framework(code="cc-test", name="CC тест", is_custom=True)
        db.add(fw)
        db.flush()
        r = Requirement(framework_id=fw.id, code="CC-1", title="Базовий", family="CC")
        db.add(r)
        db.flush()
        bl = Baseline(catalog_id=fw.id, name="CC-baseline", level=BaselineLevel.CUSTOM.value)
        db.add(bl)
        db.flush()
        db.add(BaselineItem(baseline_id=bl.id, requirement_id=r.id))
        db.commit()
        env = {"baseline_id": bl.id}
    sys = client.post("/api/systems", json={"name": "ІКС власні заходи"},
                      headers=admin_headers).json()
    env["system_id"] = sys["id"]
    env["profile_id"] = client.post(
        f"/api/systems/{sys['id']}/profiles",
        json={"baseline_id": env["baseline_id"]}, headers=admin_headers,
    ).json()["id"]
    return env


def test_add_custom_control(client, admin_headers, cc_env):
    pid = cc_env["profile_id"]
    resp = client.post(
        f"/api/profiles/{pid}/custom-control",
        json={
            "code": "ДОД-1",
            "title": "Додатковий організаційний захід",
            "description": "ДОД-1.1 Зробити X;\nДОД-1.2 Зробити Y.",
            "justification": "Вимога внутрішнього регламенту",
            "parameters": [
                {"label": "Періодичність перегляду", "default_value": "щокварталу",
                 "org_defined": False},
                {"label": "Відповідальний підрозділ", "org_defined": True},
            ],
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # доданий захід у профілі, origin=added
    cc = next(c for c in body["controls"] if c["requirement"]["code"] == "ДОД-1")
    assert cc["origin"] == "added" and cc["included"]
    # рішення tailoring зафіксовано
    assert any(d["action"] == "add" for d in body["decisions"])

    # У резолвленому поданні: прописане значення передзаповнене, org-defined потребує введення
    resolved = client.get(f"/api/profiles/{pid}/resolved", headers=admin_headers).json()
    rc = next(c for c in resolved["controls"] if c["code"] == "ДОД-1")
    by_label = {p["label"]: p for p in rc["parameters"]}
    assert by_label["Періодичність перегляду"]["value"] == "щокварталу"
    assert by_label["Відповідальний підрозділ"]["needs_input"] is True


def test_custom_control_duplicate_code_409(client, admin_headers, cc_env):
    pid = cc_env["profile_id"]
    payload = {"code": "ДОД-DUP", "title": "Дубль", "justification": "x"}
    assert client.post(
        f"/api/profiles/{pid}/custom-control", json=payload, headers=admin_headers
    ).status_code == 201
    assert client.post(
        f"/api/profiles/{pid}/custom-control", json=payload, headers=admin_headers
    ).status_code == 409


def test_custom_control_requires_justification(client, admin_headers, cc_env):
    pid = cc_env["profile_id"]
    resp = client.post(
        f"/api/profiles/{pid}/custom-control",
        json={"code": "ДОД-2", "title": "Без обґрунтування"},
        headers=admin_headers,
    )
    assert resp.status_code == 422
