import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AuditStatus(str, enum.Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    REPORTING = "reporting"
    CLOSED = "closed"


class AuditType(str, enum.Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"


class ChecklistResult(str, enum.Enum):
    COMPLIANT = "compliant"
    PARTIAL = "partial"
    NON_COMPLIANT = "non_compliant"
    NOT_APPLICABLE = "not_applicable"


class FindingSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Audit(Base):
    __tablename__ = "audits"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # AUD-001
    title: Mapped[str] = mapped_column(String(500))
    audit_type: Mapped[str] = mapped_column(String(16), default=AuditType.INTERNAL.value)
    scope: Mapped[str | None] = mapped_column(Text)
    framework_id: Mapped[int | None] = mapped_column(
        ForeignKey("frameworks.id", ondelete="SET NULL")
    )
    date_from: Mapped[date | None] = mapped_column(Date)
    date_to: Mapped[date | None] = mapped_column(Date)
    auditor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    auditor_external: Mapped[str | None] = mapped_column(String(255))  # для зовнішніх аудитів
    status: Mapped[str] = mapped_column(String(32), default=AuditStatus.PLANNED.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    framework = relationship("Framework")
    auditor = relationship("User")
    systems = relationship("InformationSystem", secondary="audit_systems")
    checklist: Mapped[list["AuditChecklistItem"]] = relationship(
        back_populates="audit", cascade="all, delete-orphan", order_by="AuditChecklistItem.id"
    )
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="audit", cascade="all, delete-orphan", order_by="Finding.id"
    )


class AuditChecklistItem(Base):
    __tablename__ = "audit_checklist_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    audit_id: Mapped[int] = mapped_column(ForeignKey("audits.id", ondelete="CASCADE"), index=True)
    requirement_id: Mapped[int | None] = mapped_column(
        ForeignKey("requirements.id", ondelete="SET NULL")
    )
    text: Mapped[str] = mapped_column(Text)  # код + назва вимоги або довільний пункт
    result: Mapped[str | None] = mapped_column(String(32))
    comment: Mapped[str | None] = mapped_column(Text)

    audit: Mapped[Audit] = relationship(back_populates="checklist")
    requirement = relationship("Requirement")


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # FND-001
    audit_id: Mapped[int] = mapped_column(ForeignKey("audits.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(16), default=FindingSeverity.MEDIUM.value)
    control_id: Mapped[int | None] = mapped_column(ForeignKey("controls.id", ondelete="SET NULL"))
    requirement_id: Mapped[int | None] = mapped_column(
        ForeignKey("requirements.id", ondelete="SET NULL")
    )
    # Породжений ризик у реєстрі (зв'язок зберігається)
    risk_id: Mapped[int | None] = mapped_column(ForeignKey("risks.id", ondelete="SET NULL"))

    # Коригувальна дія
    action_title: Mapped[str | None] = mapped_column(Text)
    responsible_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    deadline: Mapped[date | None] = mapped_column(Date)
    action_status: Mapped[str] = mapped_column(String(32), default="open")  # ActionStatus

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    audit: Mapped[Audit] = relationship(back_populates="findings")
    control = relationship("Control")
    requirement = relationship("Requirement")
    risk = relationship("Risk")
    responsible = relationship("User")
