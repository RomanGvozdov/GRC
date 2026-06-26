import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.core.deps import get_current_user, require_admin
from app.database import engine, get_db
from app.models import (
    AISuggestion,
    Control,
    InformationSystem,
    Policy,
    PolicyVersion,
    Requirement,
    User,
)
from app.services.ai import provider as ai_provider
from app.services.ai import store as ai_store
from app.services.audit import log_action

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["ai"])

_SYSTEM_PROMPT = (
    "Ти — асистент GRC-системи. Відповідай УКРАЇНСЬКОЮ і ЛИШЕ на основі наведеного "
    "контексту. Якщо контексту недостатньо — чесно скажи про це. Після кожного "
    "твердження став посилання на джерело у форматі [тип#id] (напр. [requirement#12]). "
    "Не вигадуй фактів поза контекстом."
)


_DRAFT_SYSTEM_PROMPT = (
    "Ти — асистент із кібербезпеки та відповідності (НД ТЗІ / NIST 800-53). "
    "Напиши УКРАЇНСЬКОЮ чернетку для людини-рецензента. Спирайся на наданий контекст; "
    "де бракує конкретних даних організації — постав явну позначку [ПОТРЕБУЄ УТОЧНЕННЯ], "
    "а не вигадуй. Пиши діловим стилем, по суті, структуровано. Це чернетка, яку перевірить "
    "і відредагує фахівець перед використанням."
)


class AskIn(BaseModel):
    query: str = Field(min_length=3)
    k: int = Field(default=5, ge=1, le=20)


class DraftIn(BaseModel):
    kind: str = Field(pattern="^(ssp_control|policy)$")
    requirement_id: int | None = None
    system_id: int | None = None
    topic: str | None = None
    k: int = Field(default=5, ge=0, le=20)


def _require_enabled() -> ai_provider.AIProvider:
    provider = ai_provider.get_provider()
    if not provider.enabled:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "AI вимкнено. Увімкніть AI_ENABLED і задайте AI_BASE_URL/AI_MODEL.",
        )
    return provider


@router.get("/status")
def ai_status(_: User = Depends(require_admin)):
    """Стан AI-підсистеми (без секретів)."""
    settings = get_settings()
    provider = ai_provider.get_provider()
    return {
        "enabled": provider.enabled,
        "provider": settings.ai_provider,
        "model": settings.ai_model or None,
        "embed_model": settings.ai_embed_model or None,
        "embed_dim": settings.ai_embed_dim,
        "vector_ready": ai_store.vector_ready(engine),
    }


def _collect_sources(db: Session) -> list[tuple[str, int, str]]:
    """Джерела для індексації: вимоги каталогів, контролі, діючі політики."""
    items: list[tuple[str, int, str]] = []
    for r in db.scalars(select(Requirement)):
        text = f"{r.code} {r.title}\n{r.description or ''}".strip()
        items.append(("requirement", r.id, text))
    for c in db.scalars(select(Control)):
        text = f"{c.code} {c.name}\n{c.description or ''}".strip()
        items.append(("control", c.id, text))
    for p in db.scalars(
        select(Policy).options(selectinload(Policy.versions).selectinload(PolicyVersion.policy))
    ):
        version = p.current_version
        content = (version.content_md if version else None) or ""
        if content.strip():
            items.append(("policy", p.id, f"{p.code} {p.title}\n{content}".strip()))
    return items


@router.post("/index")
def ai_index(db: Session = Depends(get_db), actor: User = Depends(require_admin)):
    """Проіндексувати джерела у векторне сховище (RAG). Лише retrieval-підготовка."""
    provider = _require_enabled()
    if not ai_store.vector_ready(engine):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Векторне сховище недоступне (потрібен PostgreSQL із розширенням vector).",
        )
    items = _collect_sources(db)
    indexed = 0
    for start in range(0, len(items), 32):
        batch = items[start : start + 32]
        embeddings = provider.embed([text for _, _, text in batch])
        for (source_type, source_id, text), emb in zip(batch, embeddings):
            ai_store.upsert_chunk(engine, source_type, source_id, text, emb)
        indexed += len(batch)
    log_action(db, actor, "ai_index", "ai", None, {"indexed": indexed})
    db.commit()
    return {"indexed": indexed}


@router.post("/ask")
def ai_ask(
    body: AskIn, db: Session = Depends(get_db), actor: User = Depends(get_current_user)
):
    """Семантичний Q&A по каталогах/контролях/політиках (RAG). Відповідь —
    лише з retrieval-контексту, з обов'язковими цитатами; результат логується
    в AISuggestion (провенанс). Стан системи не змінюється."""
    provider = _require_enabled()
    query_emb = provider.embed([body.query])[0]
    hits = ai_store.search(engine, query_emb, k=body.k)

    if not hits:
        answer = "За вашим запитом нічого не знайдено в проіндексованих джерелах."
        citations: list[dict] = []
    else:
        context = "\n\n".join(
            f"[{h['source_type']}#{h['source_id']}] {h['content']}" for h in hits
        )
        answer = provider.chat([
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Контекст:\n{context}\n\nЗапитання: {body.query}"},
        ])
        citations = [
            {"source_type": h["source_type"], "source_id": h["source_id"],
             "score": round(float(h.get("score", 0)), 4)}
            for h in hits
        ]

    suggestion = AISuggestion(
        kind="qa",
        user_id=actor.id,
        model=provider.model,
        prompt_hash=ai_provider.prompt_hash(body.query),
        query=body.query,
        output=answer,
        citations=citations,
    )
    db.add(suggestion)
    db.commit()
    return {"answer": answer, "citations": citations, "suggestion_id": suggestion.id}


@router.post("/draft-narrative")
def ai_draft_narrative(
    body: DraftIn, db: Session = Depends(get_db), actor: User = Depends(get_current_user)
):
    """AI-сценарій 2: чернетка наративу (опис впровадження SSP-контролю або текст
    політики). Human-in-the-loop: повертає чернетку + провенанс (AISuggestion),
    НЕ змінює сам артефакт — людина перевіряє й зберігає вручну."""
    provider = _require_enabled()

    if body.kind == "ssp_control":
        if body.requirement_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Вкажіть requirement_id")
        req = db.get(Requirement, body.requirement_id)
        if req is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Вимогу не знайдено")
        subject = f"{req.code} {req.title}"
        query = f"{subject}\n{req.description or ''}".strip()
        system = db.get(InformationSystem, body.system_id) if body.system_id else None
        sys_line = (
            f"ІКС: {system.name}. {system.description or ''}".strip()
            if system else "ІКС: не вказано."
        )
        task = (
            f"Напиши чернетку ОПИСУ ВПРОВАДЖЕННЯ контролю «{subject}» у цій системі — "
            f"як саме організація реалізує вимогу.\n{sys_line}\nТекст контролю: "
            f"{req.description or '—'}"
        )
    else:  # policy
        if not body.topic or not body.topic.strip():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Вкажіть topic")
        subject = body.topic.strip()
        query = subject
        task = (
            f"Напиши чернетку розділу ПОЛІТИКИ безпеки на тему «{subject}»: мета, сфера "
            f"застосування, ролі та відповідальність, основні вимоги/правила."
        )

    # Опційне RAG-заземлення (якщо доступне векторне сховище)
    citations: list[dict] = []
    context = ""
    if body.k > 0 and ai_store.vector_ready(engine):
        hits = ai_store.search(engine, provider.embed([query])[0], k=body.k)
        if hits:
            context = "\n\n".join(
                f"[{h['source_type']}#{h['source_id']}] {h['content']}" for h in hits
            )
            citations = [
                {"source_type": h["source_type"], "source_id": h["source_id"],
                 "score": round(float(h.get("score", 0)), 4)}
                for h in hits
            ]

    user_content = (f"Контекст:\n{context}\n\n{task}" if context else task)
    draft = provider.chat([
        {"role": "system", "content": _DRAFT_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ])

    suggestion = AISuggestion(
        kind=f"draft_{body.kind}",
        user_id=actor.id,
        model=provider.model,
        prompt_hash=ai_provider.prompt_hash(query),
        query=subject,
        output=draft,
        citations=citations,
    )
    db.add(suggestion)
    db.commit()
    return {"draft": draft, "citations": citations, "suggestion_id": suggestion.id}


@router.post("/suggestions/{suggestion_id}/accept")
def ai_accept_suggestion(
    suggestion_id: int, db: Session = Depends(get_db), actor: User = Depends(get_current_user)
):
    """Позначити AI-чернетку як прийняту (провенанс human-in-the-loop)."""
    s = db.get(AISuggestion, suggestion_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пропозицію не знайдено")
    s.accepted = True
    db.commit()
    return {"id": s.id, "accepted": True}


@router.get("/suggestions")
def ai_suggestions(
    db: Session = Depends(get_db), _: User = Depends(require_admin), limit: int = 50
):
    """Журнал AI-генерацій (провенанс)."""
    rows = db.scalars(
        select(AISuggestion).order_by(AISuggestion.id.desc()).limit(min(limit, 200))
    ).all()
    return [
        {
            "id": s.id, "kind": s.kind, "query": s.query, "output": s.output,
            "citations": s.citations, "accepted": s.accepted,
            "model": s.model, "created_at": s.created_at,
        }
        for s in rows
    ]
