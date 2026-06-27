import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from jinja2 import Environment, PackageLoader, select_autoescape
from openpyxl import Workbook
from sqlalchemy import func, select
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
    Assessment,
    AssessmentResult,
    Audit,
    Control,
    ControlParameter,
    Evidence,
    Finding,
    Framework,
    InformationSystem,
    POAMItem,
    Profile,
    ProfileControl,
    ProfileParameterValue,
    Requirement,
    Risk,
    SSP,
    SSPControl,
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


# --- RMF-звітність за профілем/ІКС (ТЗ §6/§8) ---

def _xlsx(headers: list[str], rows: list[list], sheet: str, filename: str) -> StreamingResponse:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet
    ws.append(headers)
    for row in rows:
        ws.append(row)
    out = io.BytesIO()
    wb.save(out)
    return StreamingResponse(
        io.BytesIO(out.getvalue()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _latest_ssp_status(db: Session, profile_id: int) -> dict[int, str]:
    """requirement_id → статус впровадження з останнього SSP профілю."""
    ssp = db.scalar(
        select(SSP).where(SSP.profile_id == profile_id)
        .order_by(SSP.id.desc()).limit(1)
        .options(selectinload(SSP.controls))
    )
    if ssp is None:
        return {}
    return {c.requirement_id: c.implementation_status for c in ssp.controls}


def _soa_rows(db: Session, profile: Profile) -> list[dict]:
    impl_by_req = _latest_ssp_status(db, profile.id)
    pv_map = {pv.parameter_id: pv.value for pv in profile.parameter_values}
    # обґрунтування tailoring за вимогою (останнє рішення)
    just_by_req: dict[int, str] = {}
    for d in profile.decisions:
        if d.requirement_id:
            just_by_req[d.requirement_id] = d.justification
    rows = []
    for pc in profile.controls:
        req = pc.requirement
        params = []
        for p in req.parameters:
            val = pv_map.get(p.id, p.default_value)
            org = bool((p.constraints or {}).get("org_defined"))
            if org and not val:
                params.append(f"{p.label}: ⚠ потребує визначення")
            elif val:
                params.append(f"{p.label}: {val}")
        rows.append({
            "code": req.code,
            "title": req.title,
            "included": "Так" if pc.included else "Ні",
            "included_key": "implemented" if pc.included else "not_applicable",
            "origin": "Доданий" if pc.origin == "added" else "Baseline",
            "status": IMPL_UA.get(impl_by_req.get(req.id, ""), "—"),
            "status_key": impl_by_req.get(req.id, "none"),
            "justification": just_by_req.get(req.id, ""),
            "params": params,
        })
    return rows


def _load_profile_for_report(db: Session, profile_id: int) -> Profile:
    profile = db.scalar(
        select(Profile).where(Profile.id == profile_id).options(
            selectinload(Profile.controls).selectinload(ProfileControl.requirement)
            .selectinload(Requirement.parameters),
            selectinload(Profile.parameter_values),
            selectinload(Profile.decisions),
            selectinload(Profile.system),
        )
    )
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Профіль не знайдено")
    return profile


@router.get("/profile/{profile_id}/soa")
def profile_soa(
    profile_id: int,
    fmt: str = Query(default="pdf", pattern="^(pdf|xlsx)$"),
    db: Session = Depends(get_db),
    _: User = Depends(require_reports),
):
    """Декларація застосовності (SoA) за цільовим профілем ІКС: контролі (включено/
    виключено), походження, статус впровадження, ODP-значення, обґрунтування."""
    profile = _load_profile_for_report(db, profile_id)
    rows = _soa_rows(db, profile)
    system = profile.system
    name = f"soa_profile_{profile_id}_{date.today().isoformat()}"
    if fmt == "xlsx":
        xlsx_rows = [
            [r["code"], r["title"], r["included"], r["origin"], r["status"],
             "; ".join(r["params"]), r["justification"]]
            for r in rows
        ]
        return _xlsx(
            ["Контроль", "Назва", "Застосовно", "Походження", "Статус впровадження",
             "ODP-параметри", "Обґрунтування"],
            xlsx_rows, "SoA", f"{name}.xlsx",
        )
    summary = {
        "total": len(rows),
        "included": sum(1 for r in rows if r["included"] == "Так"),
        "excluded": sum(1 for r in rows if r["included"] == "Ні"),
        "added": sum(1 for r in rows if r["origin"] == "Доданий"),
    }
    return _pdf(
        "soa_profile.html", f"{name}.pdf",
        profile=profile, system=system, rows=rows, summary=summary,
    )


def _readiness_data(db: Session, system: InformationSystem) -> dict:
    profile = db.scalar(
        select(Profile).where(Profile.system_id == system.id, Profile.status != "superseded")
        .order_by(Profile.id.desc()).limit(1).options(selectinload(Profile.controls))
    )
    ssp = db.scalar(
        select(SSP).where(SSP.system_id == system.id, SSP.status != "superseded")
        .order_by(SSP.id.desc()).limit(1).options(selectinload(SSP.controls))
    )
    assessment = db.scalar(
        select(Assessment).where(Assessment.system_id == system.id)
        .order_by(Assessment.id.desc()).limit(1).options(selectinload(Assessment.results))
    )
    poam_open = db.scalar(
        select(func.count(POAMItem.id)).where(
            POAMItem.system_id == system.id, POAMItem.status != "completed"
        )
    ) or 0
    stale = db.scalar(
        select(func.count(Evidence.id)).where(
            Evidence.system_id == system.id, Evidence.valid_until.isnot(None),
            Evidence.valid_until < date.today(),
        )
    ) or 0

    ssp_impl = sum(1 for c in ssp.controls if c.implementation_status == "implemented") if ssp else 0
    ssp_total = len(ssp.controls) if ssp else 0
    a_sat = sum(1 for r in assessment.results if r.result == "satisfied") if assessment else 0
    a_total = len(assessment.results) if assessment else 0

    checks = {
        "profile_approved": bool(profile and profile.status == "approved"),
        "ssp_approved": bool(ssp and ssp.status == "approved"),
        "assessed": bool(assessment and assessment.status == "completed"),
        "no_open_poam": poam_open == 0,
        "no_drift": stale == 0,
    }
    passed = sum(checks.values())
    verdict = ("authorized" if passed == len(checks)
               else "conditional" if passed >= 3 else "not_ready")
    return {
        "profile": profile, "ssp": ssp, "ssp_impl": ssp_impl, "ssp_total": ssp_total,
        "assessment": assessment, "a_sat": a_sat, "a_total": a_total,
        "poam_open": poam_open, "stale": stale, "checks": checks, "verdict": verdict,
    }


@router.get("/system/{system_id}/readiness")
def system_readiness(
    system_id: int, db: Session = Depends(get_db), _: User = Depends(require_reports)
):
    """Картка готовності ІКС до авторизації (RMF readiness): профіль → SSP →
    оцінювання → POA&M → ConMon, з підсумковим вердиктом."""
    system = db.get(InformationSystem, system_id)
    if system is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Систему не знайдено")
    data = _readiness_data(db, system)
    return _pdf(
        "readiness.html",
        f"readiness_{system.code}_{date.today().isoformat()}.pdf",
        system=system, **data,
    )
