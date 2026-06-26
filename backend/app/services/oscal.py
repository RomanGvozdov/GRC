"""Побудова OSCAL-документів (NIST, ТЗ §6/§8). Поки — System Security Plan.

Мінімальний валідний OSCAL 1.1.2 на межі обміну. UUID генеруються при кожному
виклику (документ-снапшот). control-id у OSCAL — нижній регістр (ac-2).
"""

import uuid
from datetime import datetime, timezone

OSCAL_VERSION = "1.1.2"

_STATUS_MAP = {
    "implemented": "implemented",
    "partial": "partial",
    "not_implemented": "planned",
    "not_applicable": "not-applicable",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def control_id(code: str) -> str:
    """НД ТЗІ/800-53 код → OSCAL control-id: 'AC-2(1)' → 'ac-2.1'."""
    return code.lower().replace("(", ".").replace(")", "")


def build_ssp_oscal(ssp, system, controls) -> dict:
    """controls — список SSPControl з підвантаженим .requirement."""
    implemented = []
    for c in controls:
        req = c.requirement
        implemented.append({
            "uuid": str(uuid.uuid4()),
            "control-id": control_id(req.code),
            "props": [{
                "name": "implementation-status",
                "value": _STATUS_MAP.get(c.implementation_status, "planned"),
            }],
            "statements": [{
                "statement-id": f"{control_id(req.code)}_stmt",
                "uuid": str(uuid.uuid4()),
                "by-components": [],
                "remarks": c.narrative or "Опис впровадження не задано.",
            }],
        })

    return {
        "system-security-plan": {
            "uuid": str(uuid.uuid4()),
            "metadata": {
                "title": ssp.title,
                "last-modified": _now(),
                "version": str(ssp.version),
                "oscal-version": OSCAL_VERSION,
            },
            "import-profile": {
                "href": f"#profile-{ssp.profile_id}" if ssp.profile_id else "#profile",
            },
            "system-characteristics": {
                "system-ids": [{"id": system.code}],
                "system-name": system.name,
                "description": ssp.system_description or system.description or "",
                "status": {"state": "operational"},
            },
            "control-implementation": {
                "description": f"Впровадження контролів профілю для {system.name}.",
                "implemented-requirements": implemented,
            },
        }
    }


def _param_oscal(p) -> dict:
    out = {"id": p.key}
    if p.label:
        out["label"] = p.label
    if p.default_value:
        out["values"] = [p.default_value]
    if p.guidance:
        out["guidelines"] = [{"prose": p.guidance}]
    return out


def _control_node(req, children_map, params_by_req) -> dict:
    cid = control_id(req.code)
    node = {"id": cid, "title": req.title}
    params = params_by_req.get(req.id) or []
    if params:
        node["params"] = [_param_oscal(p) for p in params]
    if req.description:
        node["parts"] = [{"id": f"{cid}_smt", "name": "statement", "prose": req.description}]
    kids = children_map.get(req.id) or []
    if kids:
        node["controls"] = [_control_node(c, children_map, params_by_req) for c in kids]
    return node


def build_catalog_oscal(framework, requirements) -> dict:
    """requirements — плоский список Requirement (з parent_id і .parameters)."""
    children_map: dict[int, list] = {}
    params_by_req: dict[int, list] = {}
    roots = []
    for r in requirements:
        params_by_req[r.id] = list(getattr(r, "parameters", []) or [])
        if r.parent_id:
            children_map.setdefault(r.parent_id, []).append(r)
        else:
            roots.append(r)

    # Групуємо кореневі контролі за родиною (клас НД ТЗІ / 800-53 family)
    groups: dict[str, list] = {}
    for r in roots:
        groups.setdefault(r.family or "OTHER", []).append(r)

    return {
        "catalog": {
            "uuid": str(uuid.uuid4()),
            "metadata": {
                "title": framework.name,
                "last-modified": _now(),
                "version": framework.version or "1.0",
                "oscal-version": OSCAL_VERSION,
            },
            "groups": [
                {
                    "id": fam.lower(),
                    "title": fam,
                    "controls": [_control_node(r, children_map, params_by_req) for r in ctrls],
                }
                for fam, ctrls in groups.items()
            ],
        }
    }


def build_profile_oscal(profile, system, resolved, decisions, catalog_ref) -> dict:
    """resolved — ResolvedProfileOut; decisions — список TailoringDecision."""
    with_ids = [control_id(c.code) for c in resolved.controls]
    set_params = []
    for c in resolved.controls:
        for p in c.parameters:
            if p.value is not None:
                set_params.append({"param-id": p.key, "values": [p.value]})

    tailoring_props = [
        {
            "name": "tailoring",
            "value": f"{d.action}:req{d.requirement_id}",
            "remarks": d.justification,
        }
        for d in decisions
    ]

    modify: dict = {}
    if set_params:
        modify["set-parameters"] = set_params

    profile_doc = {
        "uuid": str(uuid.uuid4()),
        "metadata": {
            "title": profile.name,
            "last-modified": _now(),
            "version": str(profile.version),
            "oscal-version": OSCAL_VERSION,
            "props": tailoring_props,
        },
        "imports": [{
            "href": f"#{catalog_ref}",
            "include-controls": [{"with-ids": with_ids}],
        }],
    }
    if modify:
        profile_doc["modify"] = modify
    return {"profile": profile_doc}


def build_poam_oscal(system, items) -> dict:
    """items — список POAMItem з підвантаженими .milestones."""
    poam_items = []
    for it in items:
        props = [{"name": "status", "value": it.status}]
        if it.severity:
            props.append({"name": "severity", "value": it.severity})
        if it.requirement:
            props.append({"name": "control-id", "value": control_id(it.requirement.code)})
        poam_items.append({
            "uuid": str(uuid.uuid4()),
            "title": it.title,
            "description": it.weakness or it.title,
            "props": props,
            "remarks": "; ".join(
                f"{m.title}{' (виконано)' if m.completed else ''}" for m in it.milestones
            ) or None,
        })

    return {
        "plan-of-action-and-milestones": {
            "uuid": str(uuid.uuid4()),
            "metadata": {
                "title": f"POA&M — {system.name}",
                "last-modified": _now(),
                "version": _now()[:10],
                "oscal-version": OSCAL_VERSION,
            },
            "import-ssp": {"href": f"#ssp-{system.code}"},
            "system-id": {"id": system.code},
            "poam-items": poam_items,
        }
    }
