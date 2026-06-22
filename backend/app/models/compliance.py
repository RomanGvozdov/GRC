import enum
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

control_requirements = Table(
    "control_requirements",
    Base.metadata,
    Column("control_id", ForeignKey("controls.id", ondelete="CASCADE"), primary_key=True),
    Column("requirement_id", ForeignKey("requirements.id", ondelete="CASCADE"), primary_key=True),
)


class ControlType(str, enum.Enum):
    PREVENTIVE = "preventive"
    DETECTIVE = "detective"
    CORRECTIVE = "corrective"


class ImplementationStatus(str, enum.Enum):
    NOT_IMPLEMENTED = "not_implemented"
    PARTIAL = "partial"
    IMPLEMENTED = "implemented"
    NOT_APPLICABLE = "not_applicable"


class CatalogSource(str, enum.Enum):
    MANUAL = "manual"
    OSCAL = "oscal"


class Framework(Base):
    __tablename__ = "frameworks"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)  # iso27001, nist80053, custom-ua
    name: Mapped[str] = mapped_column(String(255))
    version: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(16), default=CatalogSource.MANUAL.value)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False)

    requirements: Mapped[list["Requirement"]] = relationship(
        back_populates="framework", cascade="all, delete-orphan", order_by="Requirement.id"
    )


class Requirement(Base):
    __tablename__ = "requirements"

    id: Mapped[int] = mapped_column(primary_key=True)
    framework_id: Mapped[int] = mapped_column(
        ForeignKey("frameworks.id", ondelete="CASCADE"), index=True
    )
    # Посилення (enhancement) AC-2(1) посилається на базовий контроль AC-2
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("requirements.id", ondelete="CASCADE"), index=True
    )
    family: Mapped[str | None] = mapped_column(String(8), index=True)  # AC, AU, SC...
    code: Mapped[str] = mapped_column(String(64))  # A.5.1, AC-2, AC-2(1) ...
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    # Базові профілі, до яких належить вимога: "confidential,service" (порожньо = всі)
    profile_types: Mapped[str | None] = mapped_column(String(64))
    # Текст вимоги під конкретний профіль, коли він відрізняється:
    # {"confidential": "...", "service": "..."}; якщо немає — береться description
    profile_descriptions: Mapped[dict | None] = mapped_column(JSON)

    framework: Mapped[Framework] = relationship(back_populates="requirements")
    parent = relationship("Requirement", remote_side="Requirement.id", back_populates="children")
    children = relationship(
        "Requirement", back_populates="parent",
        cascade="all, delete-orphan", order_by="Requirement.id",
    )
    parameters = relationship(
        "ControlParameter", back_populates="requirement",
        cascade="all, delete-orphan", order_by="ControlParameter.id",
    )
    controls = relationship(
        "Control", secondary=control_requirements, back_populates="requirements"
    )


class ControlParameter(Base):
    """ODP — organization-defined parameter: місце у тексті контролю,
    яке заповнює організація під час tailoring (напр. ac-2_odp.01)."""

    __tablename__ = "control_parameters"

    id: Mapped[int] = mapped_column(primary_key=True)
    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("requirements.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(64))  # "ac-2_odp.01"
    label: Mapped[str | None] = mapped_column(String(500))
    guidance: Mapped[str | None] = mapped_column(Text)
    constraints: Mapped[dict | None] = mapped_column(JSON)  # допустимі значення/межі
    default_value: Mapped[str | None] = mapped_column(Text)

    requirement = relationship("Requirement", back_populates="parameters")


class Control(Base):
    __tablename__ = "controls"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # CTRL-001
    name: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    control_type: Mapped[str | None] = mapped_column(String(32))
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    owner = relationship("User")
    requirements = relationship(
        "Requirement", secondary=control_requirements, back_populates="controls"
    )
    risks = relationship("Risk", secondary="risk_controls", back_populates="controls")
    implementations = relationship(
        "ControlImplementation", back_populates="control",
        cascade="all, delete-orphan", order_by="ControlImplementation.id",
    )


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    implementation_id: Mapped[int] = mapped_column(
        ForeignKey("control_implementations.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(16))  # file / link
    name: Mapped[str] = mapped_column(String(500))
    url: Mapped[str | None] = mapped_column(Text)  # для kind=link
    file_path: Mapped[str | None] = mapped_column(Text)  # для kind=file
    valid_until: Mapped[date | None] = mapped_column(Date)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    implementation = relationship("ControlImplementation", back_populates="evidence")
    uploaded_by = relationship("User")
