"""Автоматизована RMF-звітність: SoA за профілем + картка готовності ІКС."""

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
def rep_env(client, admin_headers):
    with SessionLocal() as db:
        fw = Framework(code="rep-test", name="Report тест", is_custom=True)
        db.add(fw)
        db.flush()
        r1 = Requirement(framework_id=fw.id, code="RP-1", title="Контроль 1", family="RP")
        r2 = Requirement(framework_id=fw.id, code="RP-2", title="Контроль 2", family="RP")
        db.add_all([r1, r2])
        db.flush()
        db.add(ControlParameter(requirement_id=r1.id, key="rp-1_odp.01",
                                label="Період", default_value="30 днів",
                                constraints={"org_defined": False}))
        db.add(ControlParameter(requirement_id=r1.id, key="rp-1_odp.02",
                                label="Відповідальний", constraints={"org_defined": True}))
        bl = Baseline(catalog_id=fw.id, name="Rep-baseline", level=BaselineLevel.CUSTOM.value)
        db.add(bl)
        db.flush()
        db.add_all([BaselineItem(baseline_id=bl.id, requirement_id=r.id) for r in (r1, r2)])
        sysm = InformationSystem(code="SYS-REP", name="ІКС для звітів")
        db.add(sysm)
        db.commit()
        env = {"baseline_id": bl.id, "system_id": sysm.id}
    env["profile_id"] = client.post(
        f"/api/systems/{env['system_id']}/profiles",
        json={"baseline_id": env["baseline_id"]}, headers=admin_headers,
    ).json()["id"]
    # SSP, щоб у SoA був статус впровадження
    client.post(
        f"/api/systems/{env['system_id']}/ssp",
        json={"profile_id": env["profile_id"]}, headers=admin_headers,
    )
    return env


def test_profile_soa_pdf(client, admin_headers, rep_env):
    resp = client.get(
        f"/api/reports/profile/{rep_env['profile_id']}/soa", headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.content[:5] == b"%PDF-"


def test_profile_soa_xlsx(client, admin_headers, rep_env):
    resp = client.get(
        f"/api/reports/profile/{rep_env['profile_id']}/soa?fmt=xlsx", headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.content[:2] == b"PK"


def test_system_readiness_pdf(client, admin_headers, rep_env):
    resp = client.get(
        f"/api/reports/system/{rep_env['system_id']}/readiness", headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.content[:5] == b"%PDF-"
