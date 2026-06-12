import enum
from datetime import date, datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

risk_controls = Table(
    "risk_controls",
    Base.metadata,
    Column("risk_id", ForeignKey("risks.id", ondelete="CASCADE"), primary_key=True),
    Column("control_id", ForeignKey("controls.id", ondelete="CASCADE"), primary_key=True),
)


class RiskStatus(str, enum.Enum):
    DRAFT = "draft"
    IDENTIFIED = "identified"
    ASSESSED = "assessed"
    IN_TREATMENT = "in_treatment"
    MONITORED = "monitored"
    CLOSED = "closed"


class TreatmentStrategy(str, enum.Enum):
    MITIGATE = "mitigate"
    ACCEPT = "accept"
    AVOID = "avoid"
    TRANSFER = "transfer"


class ActionStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    VERIFIED = "verified"


def risk_level(likelihood: int | None, impact: int | None) -> int | None:
    if likelihood is None or impact is None:
        return None
    return likelihood * impact


def risk_level_label(score: int | None) -> str | None:
    if score is None:
        return None
    if score <= 4:
        return "low"
    if score <= 9:
        return "medium"
    if score <= 14:
        return "high"
    return "critical"


class RiskCategory(Base):
    __tablename__ = "risk_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)


class Risk(Base):
    __tablename__ = "risks"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # RISK-001
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("risk_categories.id", ondelete="SET NULL")
    )
    assets: Mapped[str | None] = mapped_column(Text)
    threat_source: Mapped[str | None] = mapped_column(Text)
    vulnerability: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    next_review_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default=RiskStatus.DRAFT.value)

    inherent_likelihood: Mapped[int | None] = mapped_column(Integer)
    inherent_impact: Mapped[int | None] = mapped_column(Integer)
    residual_likelihood: Mapped[int | None] = mapped_column(Integer)
    residual_impact: Mapped[int | None] = mapped_column(Integer)

    treatment_strategy: Mapped[str | None] = mapped_column(String(32))
    acceptance_comment: Mapped[str | None] = mapped_column(Text)
    accepted_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    category = relationship("RiskCategory")
    owner = relationship("User", foreign_keys=[owner_id])
    accepted_by = relationship("User", foreign_keys=[accepted_by_id])
    controls = relationship("Control", secondary=risk_controls, back_populates="risks")
    systems = relationship("InformationSystem", secondary="risk_systems")
    assessments: Mapped[list["RiskAssessment"]] = relationship(
        back_populates="risk", cascade="all, delete-orphan", order_by="RiskAssessment.assessed_at"
    )
    actions: Mapped[list["TreatmentAction"]] = relationship(
        back_populates="risk", cascade="all, delete-orphan", order_by="TreatmentAction.id"
    )


class RiskAssessment(Base):
    """Історія оцінок: окремий запис на кожну зміну оцінки."""

    __tablename__ = "risk_assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    risk_id: Mapped[int] = mapped_column(ForeignKey("risks.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # inherent / residual
    likelihood: Mapped[int] = mapped_column(Integer)
    impact: Mapped[int] = mapped_column(Integer)
    assessed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    risk: Mapped[Risk] = relationship(back_populates="assessments")
    assessed_by = relationship("User")


class TreatmentAction(Base):
    __tablename__ = "treatment_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    risk_id: Mapped[int] = mapped_column(ForeignKey("risks.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    deadline: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default=ActionStatus.OPEN.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    risk: Mapped[Risk] = relationship(back_populates="actions")
    assignee = relationship("User")
