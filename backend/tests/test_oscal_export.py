"""Інкремент 4B: експорт OSCAL catalog + profile (ТЗ §8)."""

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
def oscal_env():
    with SessionLocal() as db:
        fw = Framework(code="oscal-test", name="OSCAL тест", version="1.0", is_custom=True)
        db.add(fw)
        db.flush()
        base = Requirement(framework_id=fw.id, code="XO-1", title="Базовий контроль",
                           family="XO", description="Текст контролю")
        db.add(base)
        db.flush()
        enh = Requirement(framework_id=fw.id, code="XO-1(1)", title="Посилення",
                          family="XO", parent_id=base.id)
        db.add(enh)
        db.add(ControlParameter(requirement_id=base.id, key="xo-1_odp.01",
                                label="Період", default_value="30 днів"))
        bl = Baseline(catalog_id=fw.id, name="OSCAL-baseline", level=BaselineLevel.CUSTOM.value)
        db.add(bl)
        db.flush()
        db.add_all([
            BaselineItem(baseline_id=bl.id, requirement_id=base.id),
            BaselineItem(baseline_id=bl.id, requirement_id=enh.id),
        ])
        sys = InformationSystem(code="SYS-OS", name="ІКС OSCAL")
        db.add(sys)
        db.commit()
        return {"framework_id": fw.id, "baseline_id": bl.id, "system_id": sys.id,
                "base": base.id, "param_key": "xo-1_odp.01"}


def test_catalog_oscal(client, admin_headers, oscal_env):
    resp = client.get(f"/api/frameworks/{oscal_env['framework_id']}/oscal", headers=admin_headers)
    assert resp.status_code == 200
    assert "attachment" in resp.headers["content-disposition"]
    cat = resp.json()["catalog"]
    assert cat["metadata"]["oscal-version"] == "1.1.2"
    group = next(g for g in cat["groups"] if g["id"] == "xo")
    root = group["controls"][0]
    assert root["id"] == "xo-1"
    assert root["params"][0]["id"] == "xo-1_odp.01"
    assert root["params"][0]["values"] == ["30 днів"]
    # посилення вкладене у базовий контроль із трансформацією коду
    assert root["controls"][0]["id"] == "xo-1.1"


def test_profile_oscal(client, admin_headers, oscal_env):
    profile = client.post(
        f"/api/systems/{oscal_env['system_id']}/profiles",
        json={"baseline_id": oscal_env["baseline_id"]},
        headers=admin_headers,
    ).json()
    pid = profile["id"]
    # задаємо ODP-параметр через tailoring
    client.post(
        f"/api/profiles/{pid}/tailoring",
        json={"action": "modify_param",
              "parameter_id": _param_id(oscal_env),
              "value": "7 днів", "justification": "Суворіше для цієї ІКС"},
        headers=admin_headers,
    )
    resp = client.get(f"/api/profiles/{pid}/oscal", headers=admin_headers)
    assert resp.status_code == 200
    prof = resp.json()["profile"]
    assert prof["metadata"]["oscal-version"] == "1.1.2"
    with_ids = prof["imports"][0]["include-controls"][0]["with-ids"]
    assert "xo-1" in with_ids and "xo-1.1" in with_ids
    sp = {p["param-id"]: p["values"] for p in prof["modify"]["set-parameters"]}
    assert sp["xo-1_odp.01"] == ["7 днів"]
    # рішення tailoring потрапили в метадані
    assert any(p["name"] == "tailoring" for p in prof["metadata"]["props"])


def _param_id(env):
    from sqlalchemy import select
    with SessionLocal() as db:
        return db.scalar(select(ControlParameter.id).where(ControlParameter.key == env["param_key"]))
