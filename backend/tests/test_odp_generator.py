"""ODP-параметри в каталозі + передзаповнення прописаних значень генератором профілю."""


def test_catalog_has_odp_params(client, admin_headers):
    fws = client.get("/api/frameworks", headers=admin_headers).json()
    nd = next(f for f in fws if f["code"] == "nd-tzi-3-6-006-24")
    tree = client.get(
        f"/api/frameworks/{nd['id']}/controls?tree=true", headers=admin_headers
    ).json()
    ac2 = next(c for c in tree if c["code"] == "AC-2")
    assert ac2["parameters"], "AC-2 має містити ODP-параметри"
    has_prescribed = any(p["default_value"] for p in ac2["parameters"])
    has_org = any((p.get("constraints") or {}).get("org_defined") for p in ac2["parameters"])
    assert has_prescribed, "має бути хоч один прописаний параметр (default_value)"
    assert has_org, "має бути хоч один org-defined параметр"


def test_generator_prefills_prescribed_leaves_org_defined(client, admin_headers):
    baselines = client.get("/api/baselines", headers=admin_headers).json()
    nd_conf = next(b for b in baselines if b["level"] == "nd_confidential")
    sys = client.post(
        "/api/systems", json={"name": "ІКС ODP генератор"}, headers=admin_headers
    ).json()
    prof = client.post(
        f"/api/systems/{sys['id']}/profiles",
        json={"baseline_id": nd_conf["id"]},
        headers=admin_headers,
    ).json()

    resolved = client.get(
        f"/api/profiles/{prof['id']}/resolved", headers=admin_headers
    ).json()
    ac2 = next(c for c in resolved["controls"] if c["code"] == "AC-2")
    params = ac2["parameters"]
    # прописане значення — передзаповнено
    assert any((not p["org_defined"]) and p["value"] for p in params)
    # org-defined — потребує введення організацією
    org_param = next(p for p in params if p["org_defined"] and p["needs_input"])

    # Організація заповнює org-defined значення (без обґрунтування)
    r = client.put(
        f"/api/profiles/{prof['id']}/parameters/{org_param['parameter_id']}",
        json={"value": "визначений підрозділ ІБ"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    resolved2 = client.get(
        f"/api/profiles/{prof['id']}/resolved", headers=admin_headers
    ).json()
    ac2b = next(c for c in resolved2["controls"] if c["code"] == "AC-2")
    filled = next(p for p in ac2b["parameters"] if p["parameter_id"] == org_param["parameter_id"])
    assert filled["value"] == "визначений підрозділ ІБ" and filled["needs_input"] is False
