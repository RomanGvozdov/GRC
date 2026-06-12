from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models import ImplementationStatus, ProfileType, SystemCriticality, SystemStatus
from app.schemas import ORMModel, SystemBrief, UserBrief


# --- Системи (ІКС) ---

class SystemIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    owner_id: int | None = None
    criticality: SystemCriticality | None = None
    profile_type: ProfileType | None = None
    status: SystemStatus = SystemStatus.OPERATIONAL


class SystemOut(SystemBrief):
    description: str | None
    owner: UserBrief | None
    criticality: SystemCriticality | None
    profile_type: ProfileType | None
    status: SystemStatus
    created_at: datetime


# --- Впровадження контролів ---

class ImplementationIn(BaseModel):
    system_id: int | None = None  # None = вся організація
    implementation_status: ImplementationStatus = ImplementationStatus.NOT_IMPLEMENTED
    na_justification: str | None = None
    review_period_months: int | None = Field(default=None, ge=1, le=60)
    next_review_date: date | None = None


# --- Мої задачі ---

class MyTask(BaseModel):
    kind: str  # treatment_action / finding / approval / ack / risk_review / control_review / policy_review
    title: str
    entity_type: str  # risk / audit / policy / control
    entity_id: int
    entity_code: str
    due_date: date | None = None
    overdue: bool = False


# --- Імпорт з Excel ---

class ImportRowError(BaseModel):
    row: int
    message: str


class ImportReport(BaseModel):
    total_rows: int
    valid_rows: int
    errors: list[ImportRowError]
    created: int  # 0 при dry-run
    dry_run: bool
