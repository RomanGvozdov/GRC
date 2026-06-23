"""AI-інфраструктура (ТЗ §9): вимкнена за замовчуванням, провенанс-таблиця,
провайдер без мережевих викликів поки вимкнено."""

from sqlalchemy import inspect

from app.database import engine
from app.services.ai.provider import get_provider
from app.services.ai.store import vector_ready


def test_ai_status_disabled_by_default(client, admin_headers):
    resp = client.get("/api/ai/status", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is False
    assert data["vector_ready"] is False  # SQLite — pgvector недоступний
    assert data["embed_dim"] == 1024


def test_ai_status_requires_admin(client, admin_headers):
    from tests.conftest import full_login

    client.post(
        "/api/users",
        json={
            "email": "reader_ai@example.com",
            "full_name": "Читач AI",
            "password": "Zk9#vLm2@qRt7w",
            "role": "reader",
        },
        headers=admin_headers,
    )
    auth = full_login(client, "reader_ai@example.com", "Zk9#vLm2@qRt7w")
    headers = {"Authorization": f"Bearer {auth['tokens']['access_token']}"}
    assert client.get("/api/ai/status", headers=headers).status_code == 403


def test_provenance_table_exists(client):
    assert "ai_suggestions" in set(inspect(engine).get_table_names())


def test_provider_disabled_raises(client):
    provider = get_provider()
    assert provider.enabled is False
    # без мережі: вимкнений провайдер не робить викликів, а одразу падає
    import pytest

    with pytest.raises(RuntimeError):
        provider.embed(["тест"])
    assert vector_ready(engine) is False
