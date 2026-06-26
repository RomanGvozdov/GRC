"""AI-сценарій 2: драфтинг наративів (SSP-контролі / політики). Провайдер мокається."""

import app.api.ai as ai_api
from app.database import SessionLocal
from app.models import Requirement
from sqlalchemy import select


class _FakeProvider:
    enabled = True
    model = "test-model"

    def embed(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]

    def chat(self, messages, temperature=0.2):
        return "Чернетка опису впровадження. [ПОТРЕБУЄ УТОЧНЕННЯ] деталі організації."


def _a_requirement_id():
    with SessionLocal() as db:
        return db.scalar(select(Requirement.id).limit(1))


def test_draft_disabled_returns_503(client, admin_headers):
    resp = client.post(
        "/api/ai/draft-narrative",
        json={"kind": "ssp_control", "requirement_id": 1},
        headers=admin_headers,
    )
    assert resp.status_code == 503


def test_draft_ssp_control(client, admin_headers, monkeypatch):
    monkeypatch.setattr(ai_api.ai_provider, "get_provider", lambda: _FakeProvider())
    # векторне сховище недоступне (SQLite) → драфтинг працює без RAG-контексту
    rid = _a_requirement_id()
    resp = client.post(
        "/api/ai/draft-narrative",
        json={"kind": "ssp_control", "requirement_id": rid},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "Чернетка" in data["draft"]
    assert data["citations"] == []  # без векторного сховища
    sid = data["suggestion_id"]

    log = client.get("/api/ai/suggestions", headers=admin_headers).json()
    rec = next(s for s in log if s["id"] == sid)
    assert rec["kind"] == "draft_ssp_control"
    assert rec["accepted"] is False

    # Прийняти чернетку (human-in-the-loop провенанс)
    acc = client.post(f"/api/ai/suggestions/{sid}/accept", headers=admin_headers)
    assert acc.status_code == 200 and acc.json()["accepted"] is True
    log2 = client.get("/api/ai/suggestions", headers=admin_headers).json()
    assert next(s for s in log2 if s["id"] == sid)["accepted"] is True


def test_draft_policy(client, admin_headers, monkeypatch):
    monkeypatch.setattr(ai_api.ai_provider, "get_provider", lambda: _FakeProvider())
    resp = client.post(
        "/api/ai/draft-narrative",
        json={"kind": "policy", "topic": "Політика управління доступом"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["draft"]


def test_draft_ssp_requires_requirement_id(client, admin_headers, monkeypatch):
    monkeypatch.setattr(ai_api.ai_provider, "get_provider", lambda: _FakeProvider())
    resp = client.post(
        "/api/ai/draft-narrative", json={"kind": "ssp_control"}, headers=admin_headers
    )
    assert resp.status_code == 400


def test_draft_uses_rag_when_available(client, admin_headers, monkeypatch):
    monkeypatch.setattr(ai_api.ai_provider, "get_provider", lambda: _FakeProvider())
    monkeypatch.setattr(ai_api.ai_store, "vector_ready", lambda engine: True)
    monkeypatch.setattr(
        ai_api.ai_store, "search",
        lambda engine, emb, k=5: [
            {"source_type": "requirement", "source_id": 1,
             "content": "AC-2 Управління обліковими записами", "score": 0.88},
        ],
    )
    resp = client.post(
        "/api/ai/draft-narrative",
        json={"kind": "policy", "topic": "Управління обліковими записами"},
        headers=admin_headers,
    ).json()
    assert resp["citations"][0]["source_type"] == "requirement"
