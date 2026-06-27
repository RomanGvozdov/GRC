from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, field_validator

from app.models import (
    ActionStatus,
    ControlType,
    ImplementationStatus,
    RiskStatus,
    Role,
    TailoringAction,
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


class CustomRoleBrief(ORMModel):
    id: int
    name: str


class UserOut(UserBrief):
    is_active: bool
    totp_enabled: bool
    custom_role: CustomRoleBrief | None = None
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
    custom_role_id: int | None = None
    clear_custom_role: bool = False


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


class SystemBrief(ORMModel):
    id: int
    code: str
    name: str


class ControlBrief(ORMModel):
    id: int
    code: str
    name: str


class GapControl(BaseModel):
    id: int
    code: str
    name: str
    status: str | None  # ефективний статус у контексті обраної системи


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
    system_ids: list[int] = []


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
    systems: list[SystemBrief] = []

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
    source: str = "manual"
    is_custom: bool


class ControlParameterOut(ORMModel):
    id: int
    key: str
    label: str | None
    guidance: str | None
    constraints: dict | None
    default_value: str | None


class RequirementOut(ORMModel):
    id: int
    code: str
    title: str
    description: str | None
    family: str | None = None
    parent_id: int | None = None
    parameters: list[ControlParameterOut] = []
    profile_types: str | None = Field(default=None, exclude=True)

    @computed_field
    @property
    def profiles(self) -> list[str]:
        return [p for p in (self.profile_types or "").split(",") if p]


class RequirementTreeNode(RequirementOut):
    children: list["RequirementTreeNode"] = []


class RequirementBrief(ORMModel):
    id: int
    code: str
    title: str
    framework_id: int


# --- Baselines (RMF, ТЗ §5) ---

class BaselineIn(BaseModel):
    catalog_id: int
    name: str = Field(min_length=1, max_length=255)
    level: str = "custom"
    description: str | None = None
    requirement_ids: list[int] = []


class BaselineOut(ORMModel):
    id: int
    catalog_id: int
    name: str
    level: str
    description: str | None
    created_at: datetime
    item_count: int = 0


class BaselineDetailOut(BaselineOut):
    items: list[RequirementBrief] = []


# --- Profiles / tailoring (RMF, ТЗ §5) ---

class ProfileGenerateIn(BaseModel):
    baseline_id: int
    name: str | None = Field(default=None, max_length=255)


class ProfileControlOut(ORMModel):
    id: int
    requirement: RequirementBrief
    included: bool
    origin: str


class TailoringDecisionOut(ORMModel):
    id: int
    action: str
    requirement_id: int | None
    parameter_id: int | None
    value: str | None
    justification: str
    created_by: UserBrief | None
    created_at: datetime


class ProfileOut(ORMModel):
    id: int
    system_id: int
    baseline_id: int | None
    parent_profile_id: int | None
    name: str
    version: int
    status: str
    created_at: datetime
    approved_at: datetime | None
    control_count: int = 0  # включені контролі


class ProfileDetailOut(ProfileOut):
    controls: list[ProfileControlOut] = []
    decisions: list[TailoringDecisionOut] = []


class TailoringIn(BaseModel):
    action: TailoringAction
    requirement_id: int | None = None
    parameter_id: int | None = None
    value: str | None = None
    justification: str = Field(min_length=1)  # обов'язкове обґрунтування

    @field_validator("justification")
    @classmethod
    def _justification_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Обґрунтування обов'язкове")
        return v.strip()


class ResolvedParameterOut(BaseModel):
    parameter_id: int
    key: str
    label: str | None = None
    value: str | None = None  # значення профілю або default
    org_defined: bool = False  # True — заповнює організація (немає прописаного значення)
    needs_input: bool = False  # org_defined і значення ще не задано


class ResolvedControlOut(BaseModel):
    requirement_id: int
    code: str
    title: str
    description: str | None = None
    origin: str
    parameters: list[ResolvedParameterOut] = []


class ResolvedProfileOut(BaseModel):
    profile_id: int
    system_id: int
    name: str
    version: int
    status: str
    control_count: int
    controls: list[ResolvedControlOut] = []


# --- Overlays ---

class OverlayItemIn(BaseModel):
    requirement_id: int
    action: str = Field(pattern="^(add|remove)$")


class OverlayIn(BaseModel):
    catalog_id: int
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    items: list[OverlayItemIn] = []


class OverlayItemOut(ORMModel):
    id: int
    requirement_id: int
    action: str


class OverlayOut(ORMModel):
    id: int
    catalog_id: int
    name: str
    description: str | None
    created_at: datetime
    item_count: int = 0


class OverlayDetailOut(OverlayOut):
    items: list[OverlayItemOut] = []


class ApplyOverlayIn(BaseModel):
    justification: str = Field(min_length=1)

    @field_validator("justification")
    @classmethod
    def _justification_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Обґрунтування обов'язкове")
        return v.strip()


class ParamValueIn(BaseModel):
    value: str = Field(min_length=1)


class CustomParamIn(BaseModel):
    label: str = Field(min_length=1, max_length=500)
    default_value: str | None = None       # задано → прописане значення
    org_defined: bool = True               # True → заповнює організація


class CustomControlIn(BaseModel):
    """Власний (доданий) захід захисту в оформленні базових профілів."""

    code: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None          # текст заходу з підпунктами
    justification: str = Field(min_length=1)
    parameters: list[CustomParamIn] = []

    @field_validator("justification")
    @classmethod
    def _justification_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Обґрунтування обов'язкове")
        return v.strip()


# --- SSP (план безпеки системи, ТЗ §6) ---

class SSPGenerateIn(BaseModel):
    profile_id: int
    title: str | None = Field(default=None, max_length=255)
    system_description: str | None = None


class SSPControlOut(ORMModel):
    id: int
    requirement: RequirementBrief
    implementation_status: ImplementationStatus
    narrative: str | None
    responsible: UserBrief | None


class SSPControlIn(BaseModel):
    implementation_status: ImplementationStatus | None = None
    narrative: str | None = None
    responsible_id: int | None = None


class SSPOut(ORMModel):
    id: int
    system_id: int
    profile_id: int | None
    parent_ssp_id: int | None
    title: str
    version: int
    status: str
    system_description: str | None
    created_at: datetime
    approved_at: datetime | None
    control_count: int = 0
    implemented_count: int = 0


class SSPDetailOut(SSPOut):
    controls: list[SSPControlOut] = []


# --- POA&M (план дій та контрольних точок, ТЗ §6) ---

_SEVERITY = "^(low|medium|high|critical)$"


class POAMMilestoneIn(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    due_date: date | None = None


class POAMMilestoneUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    due_date: date | None = None
    completed: bool | None = None


class POAMMilestoneOut(ORMModel):
    id: int
    title: str
    due_date: date | None
    completed: bool
    completed_at: datetime | None
    created_at: datetime


class POAMItemIn(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    weakness: str | None = None
    requirement_id: int | None = None
    severity: str | None = Field(default=None, pattern=_SEVERITY)
    responsible_id: int | None = None
    due_date: date | None = None


class POAMItemUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    weakness: str | None = None
    status: str | None = Field(default=None, pattern="^(open|in_progress|completed|risk_accepted)$")
    severity: str | None = Field(default=None, pattern=_SEVERITY)
    responsible_id: int | None = None
    due_date: date | None = None


class POAMItemOut(ORMModel):
    id: int
    system_id: int
    requirement: RequirementBrief | None
    title: str
    weakness: str | None
    status: str
    severity: str | None
    source: str
    responsible: UserBrief | None
    due_date: date | None
    created_at: datetime
    milestone_count: int = 0
    milestone_done: int = 0


class POAMItemDetailOut(POAMItemOut):
    milestones: list[POAMMilestoneOut] = []


class POAMFromProfileOut(BaseModel):
    created: int
    skipped: int
    items: list[POAMItemOut] = []


# --- Оцінювання (800-53A) + ConMon (ТЗ §7) ---

class AssessmentGenerateIn(BaseModel):
    profile_id: int
    title: str | None = Field(default=None, max_length=255)


class AssessmentUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default=None, pattern="^(planned|in_progress|completed)$")


class AssessmentResultIn(BaseModel):
    result: str = Field(pattern="^(not_assessed|satisfied|other_than_satisfied)$")
    notes: str | None = None


class AssessmentResultOut(ORMModel):
    id: int
    requirement: RequirementBrief
    result: str
    notes: str | None
    assessed_at: datetime | None


class AssessmentOut(ORMModel):
    id: int
    system_id: int
    profile_id: int | None
    title: str
    status: str
    assessor: UserBrief | None
    created_at: datetime
    completed_at: datetime | None
    total: int = 0
    satisfied: int = 0
    other_than_satisfied: int = 0
    not_assessed: int = 0


class AssessmentDetailOut(AssessmentOut):
    results: list[AssessmentResultOut] = []


class EvidenceIngestIn(BaseModel):
    system_id: int
    requirement_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=500)
    url: str | None = None
    source: str = Field(default="scanner", max_length=32)
    valid_until: date | None = None


class ConMonControlOut(BaseModel):
    requirement_id: int
    code: str
    title: str
    state: str  # fresh / stale / none
    evidence_count: int
    latest_valid_until: date | None = None


class ConMonHealthOut(BaseModel):
    system_id: int
    profile_id: int | None
    total: int
    fresh: int
    stale: int
    none: int
    drift: list[ConMonControlOut] = []  # контролі з простроченими доказами


# --- Авторозрахунок ризику (ТЗ §8) ---

class RiskControlEffectivenessOut(BaseModel):
    code: str
    name: str
    status: str | None
    effectiveness: float | None


class ResidualPreviewOut(BaseModel):
    effectiveness: float
    inherent_likelihood: int | None
    inherent_impact: int | None
    computed_residual_likelihood: int | None
    computed_residual_impact: int | None
    current_residual_likelihood: int | None
    current_residual_impact: int | None
    applied: bool
    controls: list[RiskControlEffectivenessOut] = []


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
    requirement_ids: list[int] = []


class ImplementationOut(ORMModel):
    id: int
    system: SystemBrief | None
    implementation_status: ImplementationStatus
    na_justification: str | None
    review_period_months: int | None
    next_review_date: date | None
    evidence: list[EvidenceOut]


class ControlOut(ORMModel):
    id: int
    code: str
    name: str
    description: str | None
    control_type: ControlType | None
    owner: UserBrief | None
    requirements: list[RequirementBrief]
    implementations: list[ImplementationOut]
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def aggregate_status(self) -> str:
        return _agg_out(self.implementations)


def _agg_out(implementations) -> str:
    rank = {"not_implemented": 0, "partial": 1, "implemented": 2, "not_applicable": 3}
    statuses = [i.implementation_status.value for i in implementations]
    if not statuses:
        return "not_implemented"
    real = [s for s in statuses if s != "not_applicable"]
    if not real:
        return "not_applicable"
    return min(real, key=lambda s: rank[s])


class ControlListItem(BaseModel):
    id: int
    code: str
    name: str
    control_type: ControlType | None
    owner: UserBrief | None
    aggregate_status: str
    systems: list[SystemBrief]
    next_review_date: date | None  # найближча серед впроваджень
    requirements: list[RequirementBrief]


# --- Gap analysis ---

class GapRequirement(BaseModel):
    requirement: RequirementOut
    controls: list[GapControl]
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
