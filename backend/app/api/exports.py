import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import require_permission

require_reports = require_permission("reports", "read")
from app.database import get_db
from app.models import Control, Risk, User, aggregate_status, risk_level, risk_level_label

router = APIRouter(prefix="/exports", tags=["exports"])

RISK_STATUS_UA = {
    "draft": "Чернетка",
    "identified": "Ідентифікований",
    "assessed": "Оцінений",
    "in_treatment": "В обробці",
    "monitored": "Моніториться",
    "closed": "Закритий",
}
STRATEGY_UA = {
    "mitigate": "Зменшити",
    "accept": "Прийняти",
    "avoid": "Уникнути",
    "transfer": "Передати",
}
LEVEL_UA = {"low": "Низький", "medium": "Середній", "high": "Високий", "critical": "Критичний"}
IMPL_UA = {
    "not_implemented": "Не впроваджено",
    "partial": "Частково",
    "implemented": "Впроваджено",
    "not_applicable": "Не застосовно",
}
CONTROL_TYPE_UA = {
    "preventive": "Превентивний",
    "detective": "Детективний",
    "corrective": "Коригувальний",
}

RISK_HEADERS = [
    "Код", "Назва", "Категорія", "Статус", "Відповідальний", "Системи",
    "Ймовірність (притаманна)", "Вплив (притаманний)", "Рівень (притаманний)",
    "Ймовірність (залишкова)", "Вплив (залишковий)", "Рівень (залишковий)",
    "Стратегія обробки", "Дата наступного перегляду", "Пов'язані контролі",
]

CONTROL_HEADERS = [
    "Код", "Назва", "Тип", "Система", "Статус впровадження", "Відповідальний",
    "Вимоги (мапінг)", "Дата наступної перевірки", "Обґрунтування (не застосовно)",
]


def _risk_rows(db: Session) -> list[list]:
    risks = db.scalars(
        select(Risk).options(
            selectinload(Risk.category), selectinload(Risk.owner),
            selectinload(Risk.controls), selectinload(Risk.systems),
        ).order_by(Risk.id)
    ).all()
    rows = []
    for r in risks:
        inherent = risk_level(r.inherent_likelihood, r.inherent_impact)
        residual = risk_level(r.residual_likelihood, r.residual_impact)
        rows.append([
            r.code,
            r.title,
            r.category.name if r.category else "",
            RISK_STATUS_UA.get(r.status, r.status),
            r.owner.full_name if r.owner else "",
            ", ".join(s.name for s in r.systems),
            r.inherent_likelihood or "",
            r.inherent_impact or "",
            LEVEL_UA.get(risk_level_label(inherent) or "", ""),
            r.residual_likelihood or "",
            r.residual_impact or "",
            LEVEL_UA.get(risk_level_label(residual) or "", ""),
            STRATEGY_UA.get(r.treatment_strategy or "", ""),
            r.next_review_date.isoformat() if r.next_review_date else "",
            ", ".join(c.code for c in r.controls),
        ])
    return rows


def _control_rows(db: Session) -> list[list]:
    controls = db.scalars(
        select(Control).options(
            selectinload(Control.owner),
            selectinload(Control.requirements),
            selectinload(Control.implementations),
        ).order_by(Control.id)
    ).all()
    rows = []
    for c in controls:
        for impl in c.implementations or []:
            rows.append([
                c.code,
                c.name,
                CONTROL_TYPE_UA.get(c.control_type or "", ""),
                impl.system.name if impl.system else "Вся організація",
                IMPL_UA.get(impl.implementation_status, impl.implementation_status),
                c.owner.full_name if c.owner else "",
                ", ".join(req.code for req in c.requirements),
                impl.next_review_date.isoformat() if impl.next_review_date else "",
                impl.na_justification or "",
            ])
        if not c.implementations:
            rows.append([
                c.code, c.name, CONTROL_TYPE_UA.get(c.control_type or "", ""), "",
                IMPL_UA["not_implemented"], c.owner.full_name if c.owner else "",
                ", ".join(req.code for req in c.requirements), "", "",
            ])
    return rows


def _stream(headers: list[str], rows: list[list], fmt: str, base_name: str) -> StreamingResponse:
    filename = f"{base_name}_{date.today().isoformat()}.{fmt}"
    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(headers)
        writer.writerows(rows)
        # BOM, щоб Excel коректно відкривав кирилицю в CSV
        data = ("﻿" + buf.getvalue()).encode("utf-8")
        media = "text/csv; charset=utf-8"
    else:
        wb = Workbook()
        ws = wb.active
        ws.append(headers)
        for row in rows:
            ws.append(row)
        out = io.BytesIO()
        wb.save(out)
        data = out.getvalue()
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return StreamingResponse(
        io.BytesIO(data),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/risks")
def export_risks(
    fmt: str = Query(default="xlsx", pattern="^(xlsx|csv)$"),
    db: Session = Depends(get_db),
    _: User = Depends(require_reports),
):
    return _stream(RISK_HEADERS, _risk_rows(db), fmt, "risks")


@router.get("/controls")
def export_controls(
    fmt: str = Query(default="xlsx", pattern="^(xlsx|csv)$"),
    db: Session = Depends(get_db),
    _: User = Depends(require_reports),
):
    return _stream(CONTROL_HEADERS, _control_rows(db), fmt, "controls")
