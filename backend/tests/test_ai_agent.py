"""AI-сценарій 4 (агентний): RMF-bootstrap чернеток для ІКС. Провайдер мокається."""

import pytest

import app.api.ai as ai_api
from app.database import SessionLocal
from app.models import Baseline, BaselineItem, BaselineLevel, Framework, InformationSystem, Requirement


class _FakeProvider:
    enabled = True
    model = "test-model"

    def embed(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]

    def chat(self, messages, temperature=0.2):
        return "Чернетка/резюме УКРАЇНСЬКОЮ."


@pytest.fixture(scope="module")
def agent_env():
    with SessionLocal() as db:
        fw = Framework(code="agent-test", name="Agent тест", is_custom=True)
        db.add(fw)
        db.flush()
        reqs = [
            Requirement(framework_id=fw.id, code=c, title=f"Контроль {c}", family="AG")
            for c in ("AG-1", "AG-2", "AG-3")
        ]
        db.add_all(reqs)
        db.flush()
        bl = Baseline(catalog_id=fw.id, name="Agent-baseline", level=BaselineLevel.CUSTOM.value)
        db.add(bl)
        db.flush()
        db.add_all([BaselineItem(baseline_id=bl.id, requirement_id=r.id) for r in reqs])
        db.commit()
        return {"baseline_id": bl.id}


def test_agent_disabled_503(client, admin_headers):
    resp = client.post("/api/ai/agent/bootstrap-ics/1", json={}, headers=admin_headers)
    assert resp.status_code == 503


def test_agent_bootstrap(client, admin_headers, monkeypatch, agent_env):
    monkeypatch.setattr(ai_api.ai_provider, "get_provider", lambda: _FakeProvider())
    sys = client.post(
        "/api/systems", json={"name": "ІКС агент bootstrap"}, headers=admin_headers
    ).json()

    resp = client.post(
        f"/api/ai/agent/bootstrap-ics/{sys['id']}",
        json={"baseline_id": agent_env["baseline_id"], "max_narratives": 5},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["profile_id"] and data["ssp_id"]
    assert data["narratives_drafted"] == 3  # усі 3 контролі (max 5)
    assert data["poam_created"] == 3        # 3 непокриті контролі → 3 пункти POA&M
    assert data["summary"]
    assert {s["step"] for s in data["steps"]} >= {"profile", "ssp", "narratives", "poam"}

    # Артефакти реально створені як чернетки
    ssp = client.get(f"/api/ssp/{data['ssp_id']}", headers=admin_headers).json()
    assert ssp["status"] == "draft"
    assert all(c["narrative"] for c in ssp["controls"])  # наративи заповнено AI

    # Провенанс
    log = client.get("/api/ai/suggestions", headers=admin_headers).json()
    assert any(s["id"] == data["suggestion_id"] and s["kind"] == "agent" for s in log)


def test_agent_requires_categorization_or_baseline(client, admin_headers, monkeypatch):
    monkeypatch.setattr(ai_api.ai_provider, "get_provider", lambda: _FakeProvider())
    sys = client.post(
        "/api/systems", json={"name": "ІКС агент без категоризації"}, headers=admin_headers
    ).json()
    resp = client.post(
        f"/api/ai/agent/bootstrap-ics/{sys['id']}", json={}, headers=admin_headers
    )
    assert resp.status_code == 400
