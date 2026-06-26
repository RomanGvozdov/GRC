"""Інкремент 4C (data): англійський каталог NIST 800-53 Rev 5."""


def test_en_catalog_seeded(client, admin_headers):
    frameworks = client.get("/api/frameworks", headers=admin_headers).json()
    en = next((f for f in frameworks if f["code"] == "nist-800-53-r5-en"), None)
    assert en is not None, "Англійський каталог не засіявся"
    assert en["is_custom"] is False

    reqs = client.get(
        f"/api/frameworks/{en['id']}/requirements", headers=admin_headers
    ).json()
    assert len(reqs) == 1189
    by_code = {r["code"]: r for r in reqs}
    # англійські назви
    assert by_code["AC-2"]["title"] == "Account Management"
    # ієрархія: посилення → базовий контроль
    assert by_code["AC-2(1)"]["parent_id"] == by_code["AC-2"]["id"]
    # без профільного членства (data-only каталог)
    assert by_code["AC-2"]["profiles"] == []


def test_en_catalog_oscal_export(client, admin_headers):
    frameworks = client.get("/api/frameworks", headers=admin_headers).json()
    en = next(f for f in frameworks if f["code"] == "nist-800-53-r5-en")
    resp = client.get(f"/api/frameworks/{en['id']}/oscal", headers=admin_headers)
    assert resp.status_code == 200
    cat = resp.json()["catalog"]
    assert cat["metadata"]["oscal-version"] == "1.1.2"
    # 20 родин-груп
    assert len(cat["groups"]) == 20
