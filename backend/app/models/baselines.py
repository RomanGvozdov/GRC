"""RMF-конвеєр (ТЗ §5): базові набори контролів (baselines) над каталогом.

Baseline — набір вимог каталогу, що відповідає рівню впливу (NIST 800-53B
low/moderate/high) або базовому профілю НД ТЗІ (конфіденційна/службова). На його
основі далі генерується цільовий профіль ІКС (наступний зріз — Profile/tailoring).
"""

import enum
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BaselineLevel(str, enum.Enum):
    """Рівень базового набору."""

    LOW = "low"  # NIST 800-53B Low
    MODERATE = "moderate"  # NIST 800-53B Moderate
    HIGH = "high"  # NIST 800-53B High
    ND_CONFIDENTIAL = "nd_confidential"  # НД ТЗІ — конфіденційна інформація
    ND_SERVICE = "nd_service"  # НД ТЗІ — службова інформація (ДСК)
    ND_REGISTRY = "nd_registry"  # НД ТЗІ — галузевий профіль публічних е-реєстрів
    CUSTOM = "custom"  # довільний набір, складений вручну


class Baseline(Base):
    __tablename__ = "baselines"

    id: Mapped[int] = mapped_column(primary_key=True)
    catalog_id: Mapped[int] = mapped_column(
        ForeignKey("frameworks.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    level: Mapped[str] = mapped_column(String(16), default=BaselineLevel.CUSTOM.value)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    catalog = relationship("Framework")
    items: Mapped[list["BaselineItem"]] = relationship(
        back_populates="baseline", cascade="all, delete-orphan", order_by="BaselineItem.id"
    )


class BaselineItem(Base):
    __tablename__ = "baseline_items"
    __table_args__ = (
        UniqueConstraint("baseline_id", "requirement_id", name="uq_baseline_requirement"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    baseline_id: Mapped[int] = mapped_column(
        ForeignKey("baselines.id", ondelete="CASCADE"), index=True
    )
    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("requirements.id", ondelete="CASCADE"), index=True
    )

    baseline = relationship("Baseline", back_populates="items")
    requirement = relationship("Requirement")
