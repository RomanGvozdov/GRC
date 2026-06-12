import enum
from datetime import date, datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SystemStatus(str, enum.Enum):
    OPERATIONAL = "operational"
    DEVELOPMENT = "development"
    DECOMMISSIONED = "decommissioned"


class SystemCriticality(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


risk_systems = Table(
    "risk_systems",
    Base.metadata,
    Column("risk_id", ForeignKey("risks.id", ondelete="CASCADE"), primary_key=True),
    Column("system_id", ForeignKey("systems.id", ondelete="CASCADE"), primary_key=True),
)

audit_systems = Table(
    "audit_systems",
    Base.metadata,
    Column("audit_id", ForeignKey("audits.id", ondelete="CASCADE"), primary_key=True),
    Column("system_id", ForeignKey("systems.id", ondelete="CASCADE"), primary_key=True),
)

policy_systems = Table(
    "policy_systems",
    Base.metadata,
    Column("policy_id", ForeignKey("policies.id", ondelete="CASCADE"), primary_key=True),
    Column("system_id", ForeignKey("systems.id", ondelete="CASCADE"), primary_key=True),
)


class InformationSystem(Base):
    """ІКС — інформаційно-комунікаційна система, контекст роботи GRC."""

    __tablename__ = "systems"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # SYS-001
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    criticality: Mapped[str | None] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(32), default=SystemStatus.OPERATIONAL.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    owner = relationship("User")


class ControlImplementation(Base):
    """Впровадження контролю в конкретній ІКС (system_id=NULL — вся організація).

    Статус, обґрунтування NA, дати перевірки та докази ведуться окремо
    для кожної системи.
    """

    __tablename__ = "control_implementations"
    __table_args__ = (UniqueConstraint("control_id", "system_id", name="uq_control_system"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    control_id: Mapped[int] = mapped_column(
        ForeignKey("controls.id", ondelete="CASCADE"), index=True
    )
    system_id: Mapped[int | None] = mapped_column(
        ForeignKey("systems.id", ondelete="CASCADE"), index=True
    )
    implementation_status: Mapped[str] = mapped_column(String(32), default="not_implemented")
    na_justification: Mapped[str | None] = mapped_column(Text)
    review_period_months: Mapped[int | None] = mapped_column(Integer)
    next_review_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    control = relationship("Control", back_populates="implementations")
    system = relationship("InformationSystem")
    evidence = relationship(
        "Evidence", back_populates="implementation", cascade="all, delete-orphan",
        order_by="Evidence.id",
    )


_STATUS_RANK = {"not_implemented": 0, "partial": 1, "implemented": 2, "not_applicable": 3}


def aggregate_status(implementations: list["ControlImplementation"]) -> str:
    """Зведений статус контролю: найгірший серед впроваджень (NA ігнорується,
    якщо є хоч одне не-NA впровадження; без впроваджень — не впроваджено)."""
    statuses = [i.implementation_status for i in implementations]
    if not statuses:
        return "not_implemented"
    real = [s for s in statuses if s != "not_applicable"]
    if not real:
        return "not_applicable"
    return min(real, key=lambda s: _STATUS_RANK[s])


def effective_status_for_system(
    implementations: list["ControlImplementation"], system_id: int | None
) -> str | None:
    """Статус контролю в контексті системи: специфічне впровадження має
    пріоритет над загальноорганізаційним; в контексті «вся організація» —
    консервативно найгірший серед усіх."""
    if system_id is None:
        return aggregate_status(implementations) if implementations else None
    specific = next((i for i in implementations if i.system_id == system_id), None)
    if specific:
        return specific.implementation_status
    org_wide = next((i for i in implementations if i.system_id is None), None)
    return org_wide.implementation_status if org_wide else None
