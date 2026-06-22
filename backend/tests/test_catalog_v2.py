"""Інкремент 1, зріз «Каталог 2.0»: enhancements (parent/child) + ODP + family/source."""

from app.database import SessionLocal
from app.models import ControlParameter, Framework, Requirement


def test_family_and_source_on_seed(client, admin_headers):
    fws = client.get("/api/frameworks", headers=admin_headers).json()
    nist = next(f for f in fws if f["code"] == "nist80053")
    assert nist["source"] == "manual"  # seed-каталоги — manual

    reqs = client.get(
        f"/api/frameworks/{nist['id']}/requirements", headers=admin_headers
    ).json()
    ac2 = next(r for r in reqs if r["code"] == "AC-2")
    assert ac2["family"] == "AC"  # бекфіл родини з коду


def test_controls_tree_with_enhancements_and_parameters(client, admin_headers):
    # Будуємо ієрархію напряму в БД (OSCAL-імпорт — окремий зріз)
    with SessionLocal() as db:
        fw = Framework(code="cat2-test", name="Catalog2 тест", source="manual", is_custom=True)
        db.add(fw)
        db.flush()
        base = Requirement(framework_id=fw.id, code="XC-1", title="Базовий контроль", family="XC")
        db.add(base)
        db.flush()
        enh = Requirement(
            framework_id=fw.id, code="XC-1(1)", title="Посилення",
            family="XC", parent_id=base.id,
        )
        db.add(enh)
        db.add(ControlParameter(
            requirement_id=base.id, key="xc-1_odp.01",
            label="Період", guidance="Визначте період", default_value="30 днів",
        ))
        db.commit()
        fid = fw.id

    # Дерево: enhancement вкладено в базовий контроль, параметр присутній
    tree = client.get(
        f"/api/frameworks/{fid}/controls?tree=true", headers=admin_headers
    ).json()
    assert len(tree) == 1
    root = tree[0]
    assert root["code"] == "XC-1"
    assert [p["key"] for p in root["parameters"]] == ["xc-1_odp.01"]
    assert root["parameters"][0]["default_value"] == "30 днів"
    assert len(root["children"]) == 1
    assert root["children"][0]["code"] == "XC-1(1)"
    assert root["children"][0]["parent_id"] == root["id"]

    # Плоский список: обидва контролі
    flat = client.get(
        f"/api/frameworks/{fid}/controls?tree=false", headers=admin_headers
    ).json()
    assert {r["code"] for r in flat} == {"XC-1", "XC-1(1)"}
