"""Інтеграції з зовнішніми системами. Зараз — SIEM Wazuh (аналіз подій, ТЗ §7).

Аналіз подій за період — це виконання контролю AU-6 (аналіз журналів аудиту):
результат можна зберегти як автоматизований доказ для ІКС. Опційно локальний LLM
пише висновок аналітика (human-in-the-loop, провенанс у AISuggestion).
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.conmon import _resolve_requirement
from app.core.deps import get_current_user, require_admin, require_permission
from app.core.permissions import has_permission
from app.database import get_db
from app.models import AISuggestion, Evidence, InformationSystem, User
from app.services import wazuh as wazuh_svc
from app.services.ai import provider as ai_provider
from app.services.audit import log_action

from sqlalchemy.orm import Session

router = APIRouter(prefix="/integrations/wazuh", tags=["integrations"])

require_controls_read = require_permission("controls", "read")

_SIEM_PROMPT = (
    "Ти — аналітик SOC. На основі зведеної статистики подій SIEM Wazuh напиши "
    "УКРАЇНСЬКОЮ короткий висновок для журналу аналізу (контроль AU-6): загальна "
    "картина, що потребує уваги (правила з високим рівнем, аномальні агенти), "
    "рекомендовані дії. Без вигадок — лише з наведених даних; це чернетка для "
    "перевірки фахівцем."
)


class WazuhAnalyzeIn(BaseModel):
    days: int = Field(default=7, ge=1, le=90)
    min_level: int = Field(default=3, ge=0, le=15)
    system_id: int | None = None
    save_evidence: bool = False
    requirement_code: str = Field(default="AU-6", max_length=64)
    ai_summary: bool = True


def _require_enabled() -> "wazuh_svc.WazuhClient":
    client = wazuh_svc.get_client()
    if not client.enabled:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Інтеграцію з Wazuh вимкнено. Задайте WAZUH_ENABLED і WAZUH_API_URL.",
        )
    return client


@router.get("/status")
def wazuh_status(_: User = Depends(require_admin)):
    """Перевірка з'єднання: версія менеджера, зведення по агентах."""
    client = _require_enabled()
    try:
        info = client.status()
    except wazuh_svc.WazuhError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
    info["indexer_configured"] = client.indexer_ready
    return info


@router.post("/analyze")
def wazuh_analyze(
    body: WazuhAnalyzeIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_controls_read),
):
    """Аналіз подій Wazuh за період: агрегована статистика + (опц.) висновок
    локального LLM + (опц.) збереження як доказ AU-6 для ІКС."""
    client = _require_enabled()
    try:
        summary = client.alerts_summary(body.days, body.min_level)
    except wazuh_svc.WazuhError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))

    # Висновок аналітика від локального LLM (якщо AI увімкнено)
    narrative = None
    suggestion_id = None
    provider = ai_provider.get_provider()
    if body.ai_summary and provider.enabled:
        stats = (
            f"Період: {summary['days']} діб (рівень ≥{summary['min_level']}). "
            f"Всього подій: {summary['total']}. За рівнями: {summary['by_level']}. "
            f"Топ-правила: "
            + "; ".join(f"{r['rule']} — {r['count']} (макс. рівень {r['max_level']})"
                        for r in summary["top_rules"][:10])
            + ". Топ-агенти: "
            + "; ".join(f"{a['agent']} — {a['count']}" for a in summary["top_agents"][:10])
        )
        narrative = provider.chat([
            {"role": "system", "content": _SIEM_PROMPT},
            {"role": "user", "content": stats},
        ])
        suggestion = AISuggestion(
            kind="siem", user_id=actor.id, model=provider.model,
            prompt_hash=ai_provider.prompt_hash(stats),
            query=f"wazuh {summary['days']}d", output=narrative,
            citations=[{"source_type": "wazuh", "source_id": summary["days"],
                        "score": float(summary["total"])}],
        )
        db.add(suggestion)
        db.flush()
        suggestion_id = suggestion.id

    # Збереження як автоматизований доказ (AU-6) для ІКС
    evidence_id = None
    if body.save_evidence:
        if not has_permission(actor, "controls", "write"):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Збереження доказу потребує права «контролі: запис»"
            )
        if body.system_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Вкажіть system_id")
        system = db.get(InformationSystem, body.system_id)
        if system is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Систему не знайдено")
        req = _resolve_requirement(db, body.system_id, body.requirement_code)
        if req is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"Контроль «{body.requirement_code}» не знайдено",
            )
        top = summary["top_rules"][0]["rule"] if summary["top_rules"] else "—"
        evidence = Evidence(
            system_id=system.id,
            requirement_id=req.id,
            kind="link",
            name=(
                f"Wazuh: аналіз подій за {summary['days']} діб "
                f"({date.today().isoformat()}) — всього {summary['total']}, "
                f"топ: {top}"[:500]
            ),
            source="wazuh",
            automated=True,
            valid_until=date.today() + timedelta(days=30),
            uploaded_by_id=actor.id,
        )
        db.add(evidence)
        db.flush()
        evidence_id = evidence.id
        log_action(
            db, actor, "siem_analyze", "evidence", evidence.id,
            {"system_id": system.id, "control": req.code,
             "days": summary["days"], "total": summary["total"]},
        )

    db.commit()
    return {
        "summary": summary,
        "narrative": narrative,
        "suggestion_id": suggestion_id,
        "evidence_id": evidence_id,
    }
