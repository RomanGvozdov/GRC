from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import (
    ActionStatus,
    ApprovalDecision,
    AuditStatus,
    AuditType,
    ChecklistResult,
    FindingSeverity,
    PolicyStatus,
)
from app.schemas import ControlBrief, FrameworkOut, ORMModel, SystemBrief, UserBrief


# --- Audits ---

class AuditIn(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    audit_type: AuditType = AuditType.INTERNAL
    scope: str | None = None
    framework_id: int | None = None
    date_from: date | None = None
    date_to: date | None = None
    auditor_id: int | None = None
    auditor_external: str | None = None
    status: AuditStatus = AuditStatus.PLANNED
    system_ids: list[int] = []


class ChecklistItemIn(BaseModel):
    text: str = Field(min_length=1)
    requirement_id: int | None = None


class ChecklistItemUpdate(BaseModel):
    result: ChecklistResult | None = None
    comment: str | None = None


class ChecklistItemOut(ORMModel):
    id: int
    requirement_id: int | None
    text: str
    result: ChecklistResult | None
    comment: str | None


class FindingIn(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    severity: FindingSeverity = FindingSeverity.MEDIUM
    control_id: int | None = None
    requirement_id: int | None = None
    action_title: str | None = None
    responsible_id: int | None = None
    deadline: date | None = None
    action_status: ActionStatus = ActionStatus.OPEN


class RiskRef(ORMModel):
    id: int
    code: str
    title: str


class FindingOut(ORMModel):
    id: int
    code: str
    title: str
    description: str | None
    severity: FindingSeverity
    control: ControlBrief | None
    requirement_id: int | None
    risk: RiskRef | None
    action_title: str | None
    responsible: UserBrief | None
    deadline: date | None
    action_status: ActionStatus
    created_at: datetime


class AuditBrief(ORMModel):
    id: int
    code: str
    title: str
    audit_type: AuditType
    status: AuditStatus
    framework: FrameworkOut | None
    date_from: date | None
    date_to: date | None
    auditor: UserBrief | None
    auditor_external: str | None
    systems: list[SystemBrief] = []


class AuditOut(AuditBrief):
    scope: str | None
    checklist: list[ChecklistItemOut]
    findings: list[FindingOut]
    created_at: datetime


# --- Policies ---

class PolicyIn(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    owner_id: int | None = None
    next_review_date: date | None = None
    control_ids: list[int] = []
    system_ids: list[int] = []


class PolicyContentIn(BaseModel):
    content_md: str


class ApprovalOut(ORMModel):
    id: int
    approver: UserBrief
    decision: ApprovalDecision
    comment: str | None
    decided_at: datetime | None


class AckOut(ORMModel):
    id: int
    user: UserBrief
    assigned_at: datetime
    acknowledged_at: datetime | None


class PolicyVersionOut(ORMModel):
    id: int
    number: int
    content_md: str | None
    file_name: str | None
    created_by: UserBrief | None
    created_at: datetime
    approved_at: datetime | None
    activated_at: datetime | None
    approvals: list[ApprovalOut]
    acks: list[AckOut]


class PolicyVersionBrief(ORMModel):
    id: int
    number: int
    file_name: str | None
    created_at: datetime
    approved_at: datetime | None
    activated_at: datetime | None


class PolicyBrief(ORMModel):
    id: int
    code: str
    title: str
    status: PolicyStatus
    owner: UserBrief | None
    next_review_date: date | None
    systems: list[SystemBrief] = []


class PolicyListItem(PolicyBrief):
    model_config = ConfigDict(from_attributes=True)
    version_number: int | None = None
    ack_total: int = 0
    ack_done: int = 0
    pending_my_approval: bool = False
    pending_my_ack: bool = False


class PolicyOut(PolicyBrief):
    controls: list[ControlBrief]
    versions: list[PolicyVersionBrief]
    current_version: PolicyVersionOut | None
    created_at: datetime


class SubmitApprovalIn(BaseModel):
    approver_ids: list[int] = Field(min_length=1)


class DecisionIn(BaseModel):
    decision: ApprovalDecision
    comment: str | None = None


class AssignAcksIn(BaseModel):
    user_ids: list[int] = Field(min_length=1)


# --- Frameworks management ---

class RequirementIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None


class FrameworkIn(BaseModel):
    code: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=255)
    version: str | None = None


class FrameworkImportIn(FrameworkIn):
    requirements: list[RequirementIn] = []
