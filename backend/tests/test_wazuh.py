"""Інтеграція з SIEM Wazuh: аналіз подій за період + доказ AU-6. Клієнт мокається."""

from sqlalchemy import select

import app.api.integrations as integrations
from app.database import SessionLocal
from app.models import Evidence


_SUMMARY = {
    "days": 7,
    "min_level": 3,
    "total": 1234,
    "by_level": {"low": 1000, "medium": 200, "high": 34},
    "top_rules": [
        {"rule": "Multiple authentication failures", "count": 120, "max_level": 10},
        {"rule": "SSH brute force", "count": 80, "max_level": 12},
    ],
    "top_agents": [{"agent": "srv-web-01", "count": 500}],
    "per_day": [{"date": "2026-06-25", "count": 200}],
}


class _FakeWazuh:
    enabled = True
    indexer_ready = True

    def status(self):
        return {"connected": True, "version": "4.9.0", "agents": {"active": 12}}

    def alerts_summary(self, days, min_level=3):
        return dict(_SUMMARY, days=days, min_level=min_level)


class _FakeAI:
    enabled = True
    model = "test-model"

    def chat(self, messages, temperature=0.2):
        return "Висновок SOC-аналітика: увага на SSH brute force."


def test_wazuh_disabled_503(client, admin_headers):
    assert client.get("/api/integrations/wazuh/status",
                      headers=admin_headers).status_code == 503
    assert client.post("/api/integrations/wazuh/analyze", json={},
                       headers=admin_headers).status_code == 503


def test_wazuh_status(client, admin_headers, monkeypatch):
    monkeypatch.setattr(integrations.wazuh_svc, "get_client", lambda: _FakeWazuh())
    resp = client.get("/api/integrations/wazuh/status", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["version"] == "4.9.0" and data["indexer_configured"] is True


def test_wazuh_analyze_with_ai_and_evidence(client, admin_headers, monkeypatch):
    monkeypatch.setattr(integrations.wazuh_svc, "get_client", lambda: _FakeWazuh())
    monkeypatch.setattr(integrations.ai_provider, "get_provider", lambda: _FakeAI())
    system = client.post(
        "/api/systems", json={"name": "ІКС Wazuh"}, headers=admin_headers
    ).json()

    resp = client.post(
        "/api/integrations/wazuh/analyze",
        json={"days": 7, "system_id": system["id"], "save_evidence": True},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["summary"]["total"] == 1234
    assert data["summary"]["top_rules"][0]["rule"] == "Multiple authentication failures"
    assert "SSH brute force" in data["narrative"]
    assert data["suggestion_id"]  # провенанс AI-висновку
    assert data["evidence_id"]

    # Доказ прив'язано до ІКС і контролю AU-6, автоматизований, з терміном дії
    with SessionLocal() as db:
        ev = db.get(Evidence, data["evidence_id"])
        assert ev.system_id == system["id"]
        assert ev.source == "wazuh" and ev.automated is True
        assert ev.requirement.code == "AU-6"
        assert ev.valid_until is not None

    # Провенанс у журналі AI
    log = client.get("/api/ai/suggestions", headers=admin_headers).json()
    assert any(s["id"] == data["suggestion_id"] and s["kind"] == "siem" for s in log)


def test_wazuh_analyze_without_ai(client, admin_headers, monkeypatch):
    monkeypatch.setattr(integrations.wazuh_svc, "get_client", lambda: _FakeWazuh())
    # AI вимкнено (дефолт) → аналіз працює, narrative відсутній
    resp = client.post(
        "/api/integrations/wazuh/analyze", json={"days": 30}, headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["summary"]["days"] == 30
    assert data["narrative"] is None and data["evidence_id"] is None


def test_wazuh_save_evidence_requires_system(client, admin_headers, monkeypatch):
    monkeypatch.setattr(integrations.wazuh_svc, "get_client", lambda: _FakeWazuh())
    resp = client.post(
        "/api/integrations/wazuh/analyze",
        json={"save_evidence": True}, headers=admin_headers,
    )
    assert resp.status_code == 400
