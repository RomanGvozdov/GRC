"""Інкремент 4A: авторозрахунок залишкового ризику (ТЗ §8)."""

from app.database import SessionLocal
from app.models import Control, ControlImplementation, InformationSystem, Risk


def _make_risk(code, impl_status):
    """Ризик з однією ІКС і одним контролем заданого статусу впровадження."""
    with SessionLocal() as db:
        system = InformationSystem(code=f"SYS-{code}", name=f"ІКС {code}")
        db.add(system)
        db.flush()
        control = Control(code=f"CTRL-{code}", name=f"Контроль {code}")
        db.add(control)
        db.flush()
        db.add(ControlImplementation(
            control_id=control.id, system_id=system.id, implementation_status=impl_status
        ))
        risk = Risk(code=f"RISK-{code}", title=f"Ризик {code}",
                    inherent_likelihood=4, inherent_impact=4)
        risk.controls.append(control)
        risk.systems.append(system)
        db.add(risk)
        db.commit()
        return risk.id


def test_recalc_preview_implemented(client, admin_headers):
    rid = _make_risk("RC1", "implemented")
    resp = client.post(f"/api/risks/{rid}/recalc-residual", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["effectiveness"] == 1.0
    # ceil(4 * (1 - 1.0)) = 0 → підлога 1
    assert data["computed_residual_likelihood"] == 1
    assert data["computed_residual_impact"] == 4  # вплив не змінюється
    assert data["applied"] is False
    assert data["current_residual_likelihood"] is None  # прев'ю нічого не зберегло
    assert data["controls"][0]["status"] == "implemented"
    assert data["controls"][0]["effectiveness"] == 1.0


def test_recalc_apply_partial(client, admin_headers):
    rid = _make_risk("RC2", "partial")
    # apply=true → зберегти і додати запис в історію
    resp = client.post(f"/api/risks/{rid}/recalc-residual?apply=true", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["effectiveness"] == 0.5
    assert data["computed_residual_likelihood"] == 2  # ceil(4 * 0.5)
    assert data["applied"] is True

    risk = client.get(f"/api/risks/{rid}", headers=admin_headers).json()
    assert risk["residual_likelihood"] == 2
    assert risk["residual_impact"] == 4
    assert any(a["kind"] == "residual" for a in risk["assessments"])


def test_recalc_not_implemented_no_reduction(client, admin_headers):
    rid = _make_risk("RC3", "not_implemented")
    resp = client.post(f"/api/risks/{rid}/recalc-residual", headers=admin_headers).json()
    assert resp["effectiveness"] == 0.0
    assert resp["computed_residual_likelihood"] == 4  # без зменшення
