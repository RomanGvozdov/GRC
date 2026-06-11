import enum
from datetime import date, datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

policy_controls = Table(
    "policy_controls",
    Base.metadata,
    Column("policy_id", ForeignKey("policies.id", ondelete="CASCADE"), primary_key=True),
    Column("control_id", ForeignKey("controls.id", ondelete="CASCADE"), primary_key=True),
)


class PolicyStatus(str, enum.Enum):
    DRAFT = "draft"  # чернетка
    APPROVAL = "approval"  # на погодженні
    APPROVED = "approved"  # затверджена (ще не діюча)
    ACTIVE = "active"  # діюча
    REVIEW = "review"  # переглядається
    ARCHIVED = "archived"  # архівна


class ApprovalDecision(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # POL-001
    title: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(32), default=PolicyStatus.DRAFT.value)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    next_review_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    owner = relationship("User")
    controls = relationship("Control", secondary=policy_controls)
    versions: Mapped[list["PolicyVersion"]] = relationship(
        back_populates="policy", cascade="all, delete-orphan", order_by="PolicyVersion.number"
    )

    @property
    def current_version(self) -> "PolicyVersion | None":
        return self.versions[-1] if self.versions else None


class PolicyVersion(Base):
    __tablename__ = "policy_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)  # 1, 2, 3...
    content_md: Mapped[str | None] = mapped_column(Text)  # текст політики (Markdown)
    file_name: Mapped[str | None] = mapped_column(String(500))  # альтернатива: вкладений файл
    file_path: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    policy: Mapped[Policy] = relationship(back_populates="versions")
    created_by = relationship("User")
    approvals: Mapped[list["PolicyApproval"]] = relationship(
        back_populates="version", cascade="all, delete-orphan", order_by="PolicyApproval.id"
    )
    acks: Mapped[list["PolicyAck"]] = relationship(
        back_populates="version", cascade="all, delete-orphan", order_by="PolicyAck.id"
    )


class PolicyApproval(Base):
    __tablename__ = "policy_approvals"

    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(
        ForeignKey("policy_versions.id", ondelete="CASCADE"), index=True
    )
    approver_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    decision: Mapped[str] = mapped_column(String(16), default=ApprovalDecision.PENDING.value)
    comment: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    version: Mapped[PolicyVersion] = relationship(back_populates="approvals")
    approver = relationship("User")


class PolicyAck(Base):
    """Ознайомлення співробітника з діючою версією політики."""

    __tablename__ = "policy_acks"

    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(
        ForeignKey("policy_versions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    version: Mapped[PolicyVersion] = relationship(back_populates="acks")
    user = relationship("User")
