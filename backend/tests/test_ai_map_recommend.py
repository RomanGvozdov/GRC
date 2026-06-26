"""AI-сценарій 3: зіставлення контролів + рекомендація контролів під ризик.
Провайдер і векторне сховище мокаються."""

import pytest

import app.api.ai as ai_api
from app.database import SessionLocal
from app.models import Framework, Requirement, Risk


class _FakeProvider:
    enabled = True
    model = "test-model"

    def embed(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]

    def chat(self, messages, temperature=0.2):
        return "Пояснення зіставлення/рекомендації УКРАЇНСЬКОЮ."


@pytest.fixture(scope="module")
def env():
    with SessionLocal() as db:
        a = Framework(code="map-a", name="Каталог A", is_custom=True)
        b = Framework(code="map-b", name="Каталог B", is_custom=True)
        db.add_all([a, b])
        db.flush()
        src = Requirement(framework_id=a.id, code="SRC-1", title="Джерело", family="SR")
        tgt = Requirement(framework_id=b.id, code="TGT-1", title="Семантичний відповідник",
                          family="TG")
        same = Requirement(framework_id=b.id, code="SRC-1", title="Той самий код у B",
                           family="SR")
        db.add_all([src, tgt, same])
        risk = Risk(code="RISK-AI3", title="Витік даних через слабкі паролі",
                    description="Відсутня політика паролів", threat_source="Зловмисник",
                    vulnerability="Слабкі паролі")
        db.add(risk)
        db.commit()
        return {"fw_b": b.id, "src": src.id, "tgt": tgt.id, "same": same.id, "risk": risk.id}


def test_map_disabled_503(client, admin_headers):
    resp = client.post("/api/ai/map-control",
                       json={"requirement_id": 1, "target_framework_id": 1},
                       headers=admin_headers)
    assert resp.status_code == 503


def test_map_control(client, admin_headers, monkeypatch, env):
    monkeypatch.setattr(ai_api.ai_provider, "get_provider", lambda: _FakeProvider())
    monkeypatch.setattr(ai_api.ai_store, "vector_ready", lambda engine: True)
    monkeypatch.setattr(
        ai_api.ai_store, "search",
        lambda engine, emb, k=5: [
            {"source_type": "requirement", "source_id": env["tgt"],
             "content": "TGT-1", "score": 0.9},
        ],
    )
    resp = client.post(
        "/api/ai/map-control",
        json={"requirement_id": env["src"], "target_framework_id": env["fw_b"]},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    codes = {s["code"] for s in data["suggestions"]}
    # семантичний кандидат TGT-1 + точний збіг коду SRC-1 у каталозі B
    assert "TGT-1" in codes and "SRC-1" in codes
    # усі кандидати — з цільового каталогу B
    assert all(s["framework_id"] == env["fw_b"] for s in data["suggestions"])
    # точний збіг коду має score 1.0
    assert next(s for s in data["suggestions"] if s["code"] == "SRC-1")["score"] == 1.0
    assert data["rationale"]
    assert data["suggestion_id"]

    log = client.get("/api/ai/suggestions", headers=admin_headers).json()
    assert any(s["id"] == data["suggestion_id"] and s["kind"] == "map" for s in log)


def test_recommend_controls(client, admin_headers, monkeypatch, env):
    monkeypatch.setattr(ai_api.ai_provider, "get_provider", lambda: _FakeProvider())
    monkeypatch.setattr(ai_api.ai_store, "vector_ready", lambda engine: True)
    monkeypatch.setattr(
        ai_api.ai_store, "search",
        lambda engine, emb, k=5: [
            {"source_type": "requirement", "source_id": env["tgt"],
             "content": "TGT-1", "score": 0.77},
        ],
    )
    resp = client.post(
        "/api/ai/recommend-controls", json={"risk_id": env["risk"]}, headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["suggestions"][0]["requirement_id"] == env["tgt"]
    assert data["rationale"]
    log = client.get("/api/ai/suggestions", headers=admin_headers).json()
    assert any(s["id"] == data["suggestion_id"] and s["kind"] == "recommend" for s in log)


def test_recommend_requires_vector(client, admin_headers, monkeypatch, env):
    monkeypatch.setattr(ai_api.ai_provider, "get_provider", lambda: _FakeProvider())
    # vector_ready не мокано → SQLite → False → 400
    resp = client.post(
        "/api/ai/recommend-controls", json={"risk_id": env["risk"]}, headers=admin_headers
    )
    assert resp.status_code == 400
