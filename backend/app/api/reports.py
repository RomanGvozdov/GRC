import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from jinja2 import Environment, PackageLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from weasyprint import HTML

from app.api.exports import (
    CONTROL_TYPE_UA,
    IMPL_UA,
    LEVEL_UA,
    RISK_STATUS_UA,
    STRATEGY_UA,
)
from app.api.frameworks import requirement_applies, requirement_coverage
from app.core.deps import require_permission

require_reports = require_permission("reports", "read")
from app.database import get_db
from app.models import (
    Audit,
    Control,
    Finding,
    Framework,
    Requirement,
    Risk,
    User,
    risk_level,
    risk_level_label,
)

router = APIRouter(prefix="/reports", tags=["reports"])

_env = Environment(
    loader=PackageLoader("app", "templates"),
    autoescape=select_autoescape(["html"]),
)

AUDIT_STATUS_UA = {
    "planned": "Запланований",
    "in_progress": "Триває",
    "reporting": "Звіт",
    "closed": "Закритий",
}
AUDIT_TYPE_UA = {"internal": "Внутрішній", "external": "Зовнішній"}
SEVERITY_UA = {"low": "Низька", "medium": "Середня", "high": "Висока", "critical": "Критична"}
ACTION_STATUS_UA = {
    "open": "Відкрита",
    "in_progress": "В роботі",
    "done": "Виконана",
    "verified": "Перевірена",
}
RESULT_UA = {
    "compliant": "Відповідає",
    "partial": "Частково",
    "non_compliant": "Не відповідає",
    "not_applicable": "Не застосовно",
}
COVERAGE_UA = {
    "covered": "Покрито",
    "partial": "Частково",
    "not_covered": "Не покрито",
    "not_applicable": "Не застосовно",
}


def _pdf(template_name: str, filename: str, **context) -> StreamingResponse:
    context.setdefault("today", date.today().strftime("%d.%m.%Y"))
    html = _env.get_template(template_name).render(**context)
    pdf_bytes = HTML(string=html).write_pdf()
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/risk-register")
def risk_register(db: Session = Depends(get_db), _: User = Depends(require_reports)):
    risks = db.scalars(
        select(Risk).options(
            selectinload(Risk.category), selectinload(Risk.owner), selectinload(Risk.controls)
        ).order_by(Risk.id)
    ).all()
    rows = []
    for r in risks:
        residual = risk_level(r.residual_likelihood, r.residual_impact)
        rows.append({
            "code": r.code,
            "title": r.title,
            "category": r.category.name if r.category else "—",
            "status": RISK_STATUS_UA.get(r.status, r.status),
            "owner": r.owner.full_name if r.owner else "—",
            "inherent": risk_level(r.inherent_likelihood, r.inherent_impact),
            "residual": residual,
            "residual_label": LEVEL_UA.get(risk_level_label(residual) or "", "—"),
            "level_key": risk_level_label(residual) or "none",
            "strategy": STRATEGY_UA.get(r.treatment_strategy or "", "—"),
            "controls": ", ".join(c.code for c in r.controls) or "—",
        })
    return _pdf(
        "risk_register.html",
        f"risk_register_{date.today().isoformat()}.pdf",
        risks=rows,
    )


@router.get("/gap-analysis/{framework_id}")
def gap_analysis_report(
    framework_id: int,
    system_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_reports),
):
    framework = db.get(Framework, framework_id)
    if framework is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Фреймворк не знайдено")
    from app.models import InformationSystem, effective_status_for_system

    profile_type = None
    if system_id:
        system = db.get(InformationSystem, system_id)
        profile_type = system.profile_type if system else None

    requirements = db.scalars(
        select(Requirement)
        .where(Requirement.framework_id == framework_id)
        .options(selectinload(Requirement.controls).selectinload(Control.implementations))
        .order_by(Requirement.id)
    ).all()
    requirements = [r for r in requirements if requirement_applies(r, profile_type)]
    rows, counts = [], {"covered": 0, "partial": 0, "not_covered": 0, "not_applicable": 0}
    for req in requirements:
        coverage = requirement_coverage(req, system_id)
        counts[coverage] += 1
        rows.append({
            "code": req.code,
            "title": req.title,
            "coverage": COVERAGE_UA[coverage],
            "coverage_key": coverage,
            "controls": ", ".join(
                f"{c.code} ({IMPL_UA.get(effective_status_for_system(c.implementations, system_id) or '', '—')})"
                for c in req.controls
            ) or "—",
        })
    applicable = len(requirements) - counts["not_applicable"]
    percent = round(counts["covered"] / applicable * 100, 1) if applicable else 0.0
    return _pdf(
        "gap_analysis.html",
        f"gap_analysis_{framework.code}_{date.today().isoformat()}.pdf",
        framework=framework,
        rows=rows,
        counts=counts,
        percent=percent,
        total=len(requirements),
    )


@router.get("/audit/{audit_id}")
def audit_report(
    audit_id: int, db: Session = Depends(get_db), _: User = Depends(require_reports)
):
    audit = db.get(
        Audit,
        audit_id,
        options=[
            selectinload(Audit.checklist),
            selectinload(Audit.findings).selectinload(Finding.responsible),
            selectinload(Audit.findings).selectinload(Finding.risk),
            selectinload(Audit.framework),
            selectinload(Audit.auditor),
        ],
    )
    if audit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Аудит не знайдено")

    result_counts: dict[str, int] = {}
    for item in audit.checklist:
        if item.result:
            result_counts[item.result] = result_counts.get(item.result, 0) + 1
    checklist = [
        {
            "text": item.text,
            "result": RESULT_UA.get(item.result or "", "—"),
            "result_key": item.result or "none",
            "comment": item.comment or "",
        }
        for item in audit.checklist
    ]
    findings = [
        {
            "code": f.code,
            "title": f.title,
            "description": f.description or "",
            "severity": SEVERITY_UA.get(f.severity, f.severity),
            "severity_key": f.severity,
            "action": f.action_title or "—",
            "responsible": f.responsible.full_name if f.responsible else "—",
            "deadline": f.deadline.strftime("%d.%m.%Y") if f.deadline else "—",
            "action_status": ACTION_STATUS_UA.get(f.action_status, f.action_status),
            "risk_code": f.risk.code if f.risk else None,
        }
        for f in audit.findings
    ]
    return _pdf(
        "audit_report.html",
        f"audit_{audit.code}_{date.today().isoformat()}.pdf",
        audit=audit,
        audit_status=AUDIT_STATUS_UA.get(audit.status, audit.status),
        audit_type=AUDIT_TYPE_UA.get(audit.audit_type, audit.audit_type),
        auditor=(audit.auditor.full_name if audit.auditor else None) or audit.auditor_external or "—",
        period=(
            f"{audit.date_from.strftime('%d.%m.%Y') if audit.date_from else '…'} — "
            f"{audit.date_to.strftime('%d.%m.%Y') if audit.date_to else '…'}"
        ),
        checklist=checklist,
        result_counts={RESULT_UA[k]: v for k, v in result_counts.items()},
        findings=findings,
    )


@router.get("/soa")
def statement_of_applicability(
    framework_code: str = "iso27001",
    system_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_reports),
):
    """Statement of Applicability: вимоги фреймворка × контролі, статус і обґрунтування."""
    framework = db.scalar(select(Framework).where(Framework.code == framework_code))
    if framework is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Фреймворк не знайдено")
    profile_type = None
    if system_id:
        from app.models import InformationSystem

        system = db.get(InformationSystem, system_id)
        profile_type = system.profile_type if system else None

    requirements = db.scalars(
        select(Requirement)
        .where(Requirement.framework_id == framework.id)
        .options(
            selectinload(Requirement.controls).selectinload(Control.owner),
            selectinload(Requirement.controls).selectinload(Control.implementations),
        )
        .order_by(Requirement.id)
    ).all()
    requirements = [r for r in requirements if requirement_applies(r, profile_type)]
    rows = []
    for req in requirements:
        emitted = False
        for control in req.controls:
            impls = control.implementations
            if system_id:
                impls = [i for i in impls if i.system_id in (system_id, None)]
            for impl in impls:
                emitted = True
                rows.append({
                    "code": req.code,
                    "title": req.title,
                    "control": f"{control.code} {control.name}"
                    + (f" [{impl.system.name}]" if impl.system else ""),
                    "status": IMPL_UA.get(impl.implementation_status, ""),
                    "status_key": impl.implementation_status,
                    "type": CONTROL_TYPE_UA.get(control.control_type or "", "—"),
                    "owner": control.owner.full_name if control.owner else "—",
                    "justification": impl.na_justification or "",
                })
        if not emitted:
            rows.append({
                "code": req.code, "title": req.title, "control": "—",
                "status": "Не покрито", "status_key": "not_covered",
                "type": "—", "owner": "—", "justification": "",
            })
    return _pdf(
        "soa.html",
        f"soa_{framework.code}_{date.today().isoformat()}.pdf",
        framework=framework,
        rows=rows,
    )
