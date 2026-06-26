"""Інкремент 3: ConMon — авто-докази + дашборд здоров'я (ТЗ §7)."""

import pytest

from app.database import SessionLocal
from app.models import Baseline, BaselineItem, BaselineLevel, Framework, Requirement


@pytest.fixture(scope="module")
def conmon_env(client, admin_headers):
    with SessionLocal() as db:
        fw = Framework(code="conmon-test", name="ConMon тест", is_custom=True)
        db.add(fw)
        db.flush()
        reqs = [
            Requirement(framework_id=fw.id, code=c, title=f"Контроль {c}", family="CO")
            for c in ("CO-1", "CO-2", "CO-3")
        ]
        db.add_all(reqs)
        db.flush()
        bl = Baseline(catalog_id=fw.id, name="ConMon-baseline", level=BaselineLevel.CUSTOM.value)
        db.add(bl)
        db.flush()
        db.add_all([BaselineItem(baseline_id=bl.id, requirement_id=r.id) for r in reqs])
        db.commit()
        env = {"baseline_id": bl.id}

    sys = client.post("/api/systems", json={"name": "ІКС ConMon"}, headers=admin_headers).json()
    env["system_id"] = sys["id"]
    client.post(
        f"/api/systems/{sys['id']}/profiles",
        json={"baseline_id": env["baseline_id"]}, headers=admin_headers,
    )
    return env


def test_ingest_and_health(client, admin_headers, conmon_env):
    sid = conmon_env["system_id"]

    # Свіжий доказ для CO-1
    r = client.post(
        "/api/ingest/evidence",
        json={"system_id": sid, "requirement_code": "CO-1", "name": "Nessus scan",
              "source": "scanner", "valid_until": "2099-01-01"},
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "Nessus scan"

    # Прострочений доказ для CO-2
    r = client.post(
        "/api/ingest/evidence",
        json={"system_id": sid, "requirement_code": "CO-2", "name": "CIS benchmark",
              "source": "cis", "valid_until": "2000-01-01"},
        headers=admin_headers,
    )
    assert r.status_code == 201
    # CO-3 — без доказів

    health = client.get(f"/api/systems/{sid}/conmon/health", headers=admin_headers).json()
    assert health["total"] == 3
    assert health["fresh"] == 1  # CO-1
    assert health["stale"] == 1  # CO-2 (дрейф)
    assert health["none"] == 1   # CO-3
    assert [d["code"] for d in health["drift"]] == ["CO-2"]


def test_ingest_unknown_control(client, admin_headers, conmon_env):
    r = client.post(
        "/api/ingest/evidence",
        json={"system_id": conmon_env["system_id"], "requirement_code": "ZZ-99",
              "name": "x", "source": "scanner"},
        headers=admin_headers,
    )
    assert r.status_code == 404
