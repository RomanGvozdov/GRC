"""RMF-конвеєр: POA&M — план дій та контрольних точок (ТЗ §6).

Фіксує недоліки (вразливості/непокриті контролі) ІКС, відповідальних, терміни та
контрольні точки усунення. Пункти можна створювати вручну або генерувати з прогалин
профілю (непокриті/частково покриті контролі). Експорт в OSCAL/XLSX.
"""

import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class POAMStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    RISK_ACCEPTED = "risk_accepted"


class POAMSource(str, enum.Enum):
    MANUAL = "manual"
    FROM_GAP = "from_gap"  # згенеровано з прогалин профілю
    FROM_FINDING = "from_finding"  # зі знахідки аудиту


class POAMItem(Base):
    __tablename__ = "poam_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    system_id: Mapped[int] = mapped_column(
        ForeignKey("systems.id", ondelete="CASCADE"), index=True
    )
    requirement_id: Mapped[int | None] = mapped_column(
        ForeignKey("requirements.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(500))
    weakness: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default=POAMStatus.OPEN.value)
    severity: Mapped[str | None] = mapped_column(String(16))  # low/medium/high/critical
    source: Mapped[str] = mapped_column(String(16), default=POAMSource.MANUAL.value)
    responsible_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    due_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    system = relationship("InformationSystem")
    requirement = relationship("Requirement")
    responsible = relationship("User")
    milestones: Mapped[list["POAMMilestone"]] = relationship(
        back_populates="item", cascade="all, delete-orphan", order_by="POAMMilestone.id"
    )


class POAMMilestone(Base):
    __tablename__ = "poam_milestones"

    id: Mapped[int] = mapped_column(primary_key=True)
    poam_item_id: Mapped[int] = mapped_column(
        ForeignKey("poam_items.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(500))
    due_date: Mapped[date | None] = mapped_column(Date)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    item = relationship("POAMItem", back_populates="milestones")
