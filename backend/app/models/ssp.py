"""RMF-конвеєр, крок «Implement/Document» (ТЗ §6): SSP — план безпеки системи.

SSP документує, як впроваджено кожен контроль цільового профілю ІКС. Генерується з
резолвленого профілю (по одному `SSPControl` на включений контроль), наративи заповнює
людина. Версіонується й затверджується (як профіль). Експортується в OSCAL/PDF/XLSX.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SSPStatus(str, enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


class SSP(Base):
    __tablename__ = "ssps"

    id: Mapped[int] = mapped_column(primary_key=True)
    system_id: Mapped[int] = mapped_column(
        ForeignKey("systems.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL")
    )
    parent_ssp_id: Mapped[int | None] = mapped_column(
        ForeignKey("ssps.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default=SSPStatus.DRAFT.value)
    system_description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    system = relationship("InformationSystem")
    profile = relationship("Profile")
    approved_by = relationship("User")
    controls: Mapped[list["SSPControl"]] = relationship(
        back_populates="ssp", cascade="all, delete-orphan", order_by="SSPControl.id"
    )


class SSPControl(Base):
    __tablename__ = "ssp_controls"
    __table_args__ = (
        UniqueConstraint("ssp_id", "requirement_id", name="uq_ssp_requirement"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ssp_id: Mapped[int] = mapped_column(ForeignKey("ssps.id", ondelete="CASCADE"), index=True)
    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("requirements.id", ondelete="CASCADE"), index=True
    )
    implementation_status: Mapped[str] = mapped_column(String(32), default="not_implemented")
    narrative: Mapped[str | None] = mapped_column(Text)
    responsible_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    ssp = relationship("SSP", back_populates="controls")
    requirement = relationship("Requirement")
    responsible = relationship("User")
