from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AISuggestion(Base):
    """Провенанс AI-генерацій (ТЗ §9 guardrails): кожна підказка AI логується
    з моделлю, хешем промпта, цитатами на джерела й статусом затвердження.
    AI ніколи не пише фінальний стан напряму — лише пропонує."""

    __tablename__ = "ai_suggestions"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))  # qa / draft / mapping / triage
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    model: Mapped[str | None] = mapped_column(String(128))
    prompt_hash: Mapped[str | None] = mapped_column(String(64))
    query: Mapped[str | None] = mapped_column(Text)
    output: Mapped[str | None] = mapped_column(Text)
    citations: Mapped[list | None] = mapped_column(JSON)  # [{source_type, source_id, ...}]
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    user = relationship("User")
