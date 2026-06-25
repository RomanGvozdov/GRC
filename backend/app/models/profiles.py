"""RMF-конвеєр, крок «Select» (ТЗ §5): цільовий профіль ІКС + tailoring.

З baseline генерується цільовий профіль (`Profile`) — набір контролів
(`ProfileControl`) для конкретної ІКС. Профіль адаптується (tailoring): додавання/
вилучення контролів і задання значень ODP-параметрів — кожне рішення фіксується в
`TailoringDecision` з **обов'язковим обґрунтуванням**. Профіль версіонується й
затверджується; затверджений профіль незмінний (зміни — через нову версію).
`Overlay` — повторно застосовний набір рішень над каталогом.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProfileStatus(str, enum.Enum):
    DRAFT = "draft"  # редагується (tailoring дозволено)
    APPROVED = "approved"  # затверджено, незмінний
    SUPERSEDED = "superseded"  # замінено новою версією


class ControlOrigin(str, enum.Enum):
    BASELINE = "baseline"  # успадковано з baseline
    ADDED = "added"  # додано під час tailoring


class TailoringAction(str, enum.Enum):
    ADD = "add"  # додати контроль поза baseline
    REMOVE = "remove"  # вилучити контроль baseline
    MODIFY_PARAM = "modify_param"  # задати/змінити значення ODP-параметра


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    system_id: Mapped[int] = mapped_column(
        ForeignKey("systems.id", ondelete="CASCADE"), index=True
    )
    baseline_id: Mapped[int | None] = mapped_column(
        ForeignKey("baselines.id", ondelete="SET NULL")
    )
    parent_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default=ProfileStatus.DRAFT.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    system = relationship("InformationSystem")
    baseline = relationship("Baseline")
    approved_by = relationship("User")
    controls: Mapped[list["ProfileControl"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", order_by="ProfileControl.id"
    )
    decisions: Mapped[list["TailoringDecision"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan",
        order_by="TailoringDecision.id",
    )
    parameter_values: Mapped[list["ProfileParameterValue"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan",
        order_by="ProfileParameterValue.id",
    )


class ProfileControl(Base):
    __tablename__ = "profile_controls"
    __table_args__ = (
        UniqueConstraint("profile_id", "requirement_id", name="uq_profile_requirement"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("requirements.id", ondelete="CASCADE"), index=True
    )
    included: Mapped[bool] = mapped_column(Boolean, default=True)  # False = вилучено tailoring
    origin: Mapped[str] = mapped_column(String(16), default=ControlOrigin.BASELINE.value)

    profile = relationship("Profile", back_populates="controls")
    requirement = relationship("Requirement")


class TailoringDecision(Base):
    __tablename__ = "tailoring_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    requirement_id: Mapped[int | None] = mapped_column(
        ForeignKey("requirements.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(16))  # TailoringAction
    justification: Mapped[str] = mapped_column(Text, nullable=False)  # обов'язкове
    parameter_id: Mapped[int | None] = mapped_column(
        ForeignKey("control_parameters.id", ondelete="SET NULL")
    )
    value: Mapped[str | None] = mapped_column(Text)  # для modify_param
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    profile = relationship("Profile", back_populates="decisions")
    requirement = relationship("Requirement")
    created_by = relationship("User")


class ProfileParameterValue(Base):
    """Значення ODP-параметра в межах профілю (результат tailoring параметра)."""

    __tablename__ = "profile_parameter_values"
    __table_args__ = (
        UniqueConstraint("profile_id", "parameter_id", name="uq_profile_parameter"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    parameter_id: Mapped[int] = mapped_column(
        ForeignKey("control_parameters.id", ondelete="CASCADE"), index=True
    )
    value: Mapped[str] = mapped_column(Text)

    profile = relationship("Profile", back_populates="parameter_values")
    parameter = relationship("ControlParameter")


class Overlay(Base):
    """Повторно застосовний набір рішень tailoring над каталогом (overlay)."""

    __tablename__ = "overlays"

    id: Mapped[int] = mapped_column(primary_key=True)
    catalog_id: Mapped[int] = mapped_column(
        ForeignKey("frameworks.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    catalog = relationship("Framework")
    items: Mapped[list["OverlayItem"]] = relationship(
        back_populates="overlay", cascade="all, delete-orphan", order_by="OverlayItem.id"
    )


class OverlayItem(Base):
    __tablename__ = "overlay_items"
    __table_args__ = (
        UniqueConstraint("overlay_id", "requirement_id", name="uq_overlay_requirement"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    overlay_id: Mapped[int] = mapped_column(
        ForeignKey("overlays.id", ondelete="CASCADE"), index=True
    )
    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("requirements.id", ondelete="CASCADE"), index=True
    )
    action: Mapped[str] = mapped_column(String(16))  # add / remove

    overlay = relationship("Overlay", back_populates="items")
    requirement = relationship("Requirement")
