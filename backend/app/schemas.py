from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field

from app.models import (
    ActionStatus,
    ControlType,
    ImplementationStatus,
    RiskStatus,
    Role,
    TreatmentStrategy,
    risk_level,
    risk_level_label,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Auth ---

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    totp_code: str | None = None
    recovery_code: str | None = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginResponse(BaseModel):
    status: str  # ok / totp_setup_required
    tokens: TokenPair | None = None
    setup_token: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class TotpSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str


class TotpVerifyRequest(BaseModel):
    code: str


class TotpVerifyResponse(BaseModel):
    tokens: TokenPair
    recovery_codes: list[str]


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12)


# --- Users ---

class UserBrief(ORMModel):
    id: int
    email: EmailStr
    full_name: str
    role: Role


class UserOut(UserBrief):
    is_active: bool
    totp_enabled: bool
    created_at: datetime


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str = Field(min_length=12)
    role: Role


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=12)
    reset_totp: bool = False


# --- Dictionaries ---

class CategoryOut(ORMModel):
    id: int
    name: str


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)


# --- Risks ---

class TreatmentActionIn(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    assignee_id: int | None = None
    deadline: date | None = None
    status: ActionStatus = ActionStatus.OPEN


class TreatmentActionOut(ORMModel):
    id: int
    title: str
    assignee: UserBrief | None
    deadline: date | None
    status: ActionStatus
    created_at: datetime


class AssessmentIn(BaseModel):
    kind: str = Field(pattern="^(inherent|residual)$")
    likelihood: int = Field(ge=1, le=5)
    impact: int = Field(ge=1, le=5)


class AssessmentOut(ORMModel):
    id: int
    kind: str
    likelihood: int
    impact: int
    assessed_by: UserBrief | None
    assessed_at: datetime


class ControlBrief(ORMModel):
    id: int
    code: str
    name: str
    implementation_status: ImplementationStatus


class RiskIn(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    category_id: int | None = None
    assets: str | None = None
    threat_source: str | None = None
    vulnerability: str | None = None
    owner_id: int | None = None
    next_review_date: date | None = None
    status: RiskStatus = RiskStatus.DRAFT
    treatment_strategy: TreatmentStrategy | None = None
    acceptance_comment: str | None = None


class RiskBrief(ORMModel):
    id: int
    code: str
    title: str
    status: RiskStatus
    category: CategoryOut | None
    owner: UserBrief | None
    next_review_date: date | None
    inherent_likelihood: int | None
    inherent_impact: int | None
    residual_likelihood: int | None
    residual_impact: int | None
    treatment_strategy: TreatmentStrategy | None

    @computed_field
    @property
    def inherent_score(self) -> int | None:
        return risk_level(self.inherent_likelihood, self.inherent_impact)

    @computed_field
    @property
    def residual_score(self) -> int | None:
        return risk_level(self.residual_likelihood, self.residual_impact)

    @computed_field
    @property
    def residual_level(self) -> str | None:
        return risk_level_label(self.residual_score)


class RiskOut(RiskBrief):
    description: str | None
    assets: str | None
    threat_source: str | None
    vulnerability: str | None
    acceptance_comment: str | None
    accepted_by: UserBrief | None
    accepted_at: datetime | None
    controls: list[ControlBrief]
    assessments: list[AssessmentOut]
    actions: list[TreatmentActionOut]
    created_at: datetime
    updated_at: datetime


# --- Compliance ---

class FrameworkOut(ORMModel):
    id: int
    code: str
    name: str
    version: str | None
    is_custom: bool


class RequirementOut(ORMModel):
    id: int
    code: str
    title: str
    description: str | None


class RequirementBrief(ORMModel):
    id: int
    code: str
    title: str
    framework_id: int


class EvidenceOut(ORMModel):
    id: int
    kind: str
    name: str
    url: str | None
    valid_until: date | None
    uploaded_by: UserBrief | None
    created_at: datetime


class EvidenceLinkIn(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    url: str = Field(min_length=1)
    valid_until: date | None = None


class ControlIn(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    description: str | None = None
    control_type: ControlType | None = None
    owner_id: int | None = None
    implementation_status: ImplementationStatus = ImplementationStatus.NOT_IMPLEMENTED
    na_justification: str | None = None
    review_period_months: int | None = Field(default=None, ge=1, le=60)
    next_review_date: date | None = None
    requirement_ids: list[int] = []


class ControlOut(ORMModel):
    id: int
    code: str
    name: str
    description: str | None
    control_type: ControlType | None
    owner: UserBrief | None
    implementation_status: ImplementationStatus
    na_justification: str | None
    review_period_months: int | None
    next_review_date: date | None
    requirements: list[RequirementBrief]
    evidence: list[EvidenceOut]
    created_at: datetime
    updated_at: datetime


class ControlListItem(ORMModel):
    id: int
    code: str
    name: str
    control_type: ControlType | None
    owner: UserBrief | None
    implementation_status: ImplementationStatus
    next_review_date: date | None
    requirements: list[RequirementBrief]


# --- Gap analysis ---

class GapRequirement(BaseModel):
    requirement: RequirementOut
    controls: list[ControlBrief]
    coverage: str  # covered / partial / not_covered / not_applicable


class GapSummary(BaseModel):
    framework: FrameworkOut
    total: int
    covered: int
    partial: int
    not_covered: int
    not_applicable: int
    coverage_percent: float
    requirements: list[GapRequirement]


# --- Comments ---

class CommentIn(BaseModel):
    text: str = Field(min_length=1)


class CommentOut(ORMModel):
    id: int
    author: UserBrief | None
    text: str
    created_at: datetime


# --- Audit log ---

class AuditEntryOut(ORMModel):
    id: int
    user: UserBrief | None
    action: str
    entity_type: str
    entity_id: str | None
    details: dict | None
    created_at: datetime


# --- Dashboard ---

class HeatMapCell(BaseModel):
    likelihood: int
    impact: int
    count: int


class FrameworkCoverage(BaseModel):
    framework: FrameworkOut
    coverage_percent: float
    covered: int
    total: int


class DashboardOut(BaseModel):
    risks_total: int
    risks_by_status: dict[str, int]
    risks_by_level: dict[str, int]
    heat_map: list[HeatMapCell]
    top_risks: list[RiskBrief]
    overdue_risk_reviews: int
    overdue_control_reviews: int
    overdue_actions: int
    overdue_policy_reviews: int
    frameworks: list[FrameworkCoverage]
