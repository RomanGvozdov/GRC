import enum
from datetime import date, datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Table, Text
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


class Framework(Base):
    __tablename__ = "frameworks"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)  # iso27001, nist80053, custom-ua
    name: Mapped[str] = mapped_column(String(255))
    version: Mapped[str | None] = mapped_column(String(64))
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
    code: Mapped[str] = mapped_column(String(64))  # A.5.1, AC-2, ...
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)

    framework: Mapped[Framework] = relationship(back_populates="requirements")
    controls = relationship(
        "Control", secondary=control_requirements, back_populates="requirements"
    )


class Control(Base):
    __tablename__ = "controls"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # CTRL-001
    name: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    control_type: Mapped[str | None] = mapped_column(String(32))
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    implementation_status: Mapped[str] = mapped_column(
        String(32), default=ImplementationStatus.NOT_IMPLEMENTED.value
    )
    # Обґрунтування обов'язкове для статусу "не застосовно" (основа для SoA)
    na_justification: Mapped[str | None] = mapped_column(Text)
    review_period_months: Mapped[int | None] = mapped_column(Integer)
    next_review_date: Mapped[date | None] = mapped_column(Date)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    owner = relationship("User")
    requirements = relationship(
        "Requirement", secondary=control_requirements, back_populates="controls"
    )
    risks = relationship("Risk", secondary="risk_controls", back_populates="controls")
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="control", cascade="all, delete-orphan", order_by="Evidence.id"
    )


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    control_id: Mapped[int] = mapped_column(ForeignKey("controls.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # file / link
    name: Mapped[str] = mapped_column(String(500))
    url: Mapped[str | None] = mapped_column(Text)  # для kind=link
    file_path: Mapped[str | None] = mapped_column(Text)  # для kind=file
    valid_until: Mapped[date | None] = mapped_column(Date)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    control: Mapped[Control] = relationship(back_populates="evidence")
    uploaded_by = relationship("User")
