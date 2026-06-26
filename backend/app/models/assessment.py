"""RMF-конвеєр, крок «Assess» (ТЗ §7): оцінювання контролів (800-53A).

Оцінювання прив'язане до ІКС (і, опційно, профілю/SSP). Для кожного контролю —
результат satisfied / other-than-satisfied. Незадоволені контролі можна перенести
в POA&M. Безперервний моніторинг (ConMon) — через авто-докази (Evidence.automated).
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


class AssessmentStatus(str, enum.Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class AssessmentResultValue(str, enum.Enum):
    NOT_ASSESSED = "not_assessed"
    SATISFIED = "satisfied"
    OTHER_THAN_SATISFIED = "other_than_satisfied"


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    system_id: Mapped[int] = mapped_column(
        ForeignKey("systems.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default=AssessmentStatus.PLANNED.value)
    assessor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    system = relationship("InformationSystem")
    profile = relationship("Profile")
    assessor = relationship("User")
    results: Mapped[list["AssessmentResult"]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan",
        order_by="AssessmentResult.id",
    )


class AssessmentResult(Base):
    __tablename__ = "assessment_results"
    __table_args__ = (
        UniqueConstraint("assessment_id", "requirement_id", name="uq_assessment_requirement"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessments.id", ondelete="CASCADE"), index=True
    )
    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("requirements.id", ondelete="CASCADE"), index=True
    )
    result: Mapped[str] = mapped_column(
        String(24), default=AssessmentResultValue.NOT_ASSESSED.value
    )
    notes: Mapped[str | None] = mapped_column(Text)
    assessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assessed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    assessment = relationship("Assessment", back_populates="results")
    requirement = relationship("Requirement")
