"""AI-сценарій 1: семантичний Q&A (RAG). Провайдер і сховище мокаються —
жодних реальних мережевих викликів чи pgvector у тестах."""

import app.api.ai as ai_api


class _FakeProvider:
    enabled = True
    model = "test-model"

    def embed(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]

    def chat(self, messages, temperature=0.2):
        return "Відповідь на основі контексту [requirement#1]."


def test_ask_disabled_returns_503(client, admin_headers):
    # За замовчуванням AI вимкнено
    resp = client.post("/api/ai/ask", json={"query": "що таке контроль доступу?"},
                       headers=admin_headers)
    assert resp.status_code == 503


def test_ask_with_mocked_provider_records_provenance(client, admin_headers, monkeypatch):
    monkeypatch.setattr(ai_api.ai_provider, "get_provider", lambda: _FakeProvider())
    monkeypatch.setattr(
        ai_api.ai_store, "search",
        lambda engine, emb, k=5: [
            {"source_type": "requirement", "source_id": 1,
             "content": "AC-1 Політика контролю доступу", "score": 0.91},
        ],
    )

    resp = client.post(
        "/api/ai/ask", json={"query": "Розкажи про політику контролю доступу"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "[requirement#1]" in data["answer"]
    assert data["citations"][0]["source_type"] == "requirement"
    assert data["suggestion_id"]

    # Провенанс записано
    log = client.get("/api/ai/suggestions", headers=admin_headers).json()
    assert any(s["id"] == data["suggestion_id"] and s["kind"] == "qa" for s in log)


def test_ask_no_hits(client, admin_headers, monkeypatch):
    monkeypatch.setattr(ai_api.ai_provider, "get_provider", lambda: _FakeProvider())
    monkeypatch.setattr(ai_api.ai_store, "search", lambda engine, emb, k=5: [])
    resp = client.post(
        "/api/ai/ask", json={"query": "невідома тема xyz"}, headers=admin_headers
    )
    assert resp.status_code == 200
    assert resp.json()["citations"] == []


def test_index_requires_vector_store(client, admin_headers, monkeypatch):
    monkeypatch.setattr(ai_api.ai_provider, "get_provider", lambda: _FakeProvider())
    # vector_ready=False (SQLite) → 400 зрозуміла помилка
    resp = client.post("/api/ai/index", headers=admin_headers)
    assert resp.status_code == 400


def test_index_with_mocked_store(client, admin_headers, monkeypatch):
    monkeypatch.setattr(ai_api.ai_provider, "get_provider", lambda: _FakeProvider())
    monkeypatch.setattr(ai_api.ai_store, "vector_ready", lambda engine: True)
    calls = []
    monkeypatch.setattr(
        ai_api.ai_store, "upsert_chunk",
        lambda engine, st, sid, content, emb: calls.append((st, sid)),
    )
    resp = client.post("/api/ai/index", headers=admin_headers)
    assert resp.status_code == 200
    # Проіндексовано принаймні seed-вимоги (ISO/NIST/НД ТЗІ)
    assert resp.json()["indexed"] > 100
    assert any(st == "requirement" for st, _ in calls)
