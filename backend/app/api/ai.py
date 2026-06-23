from fastapi import APIRouter, Depends

from app.config import get_settings
from app.core.deps import require_admin
from app.database import engine
from app.models import User
from app.services.ai.provider import get_provider
from app.services.ai.store import vector_ready

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/status")
def ai_status(_: User = Depends(require_admin)):
    """Стан AI-підсистеми (без секретів). Базова інфраструктура; сценарії
    (Q&A, драфтинг) додаються наступними зрізами."""
    settings = get_settings()
    provider = get_provider()
    return {
        "enabled": provider.enabled,
        "provider": settings.ai_provider,
        "model": settings.ai_model or None,
        "embed_model": settings.ai_embed_model or None,
        "embed_dim": settings.ai_embed_dim,
        "vector_ready": vector_ready(engine),
    }
