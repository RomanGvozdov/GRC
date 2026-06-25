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
