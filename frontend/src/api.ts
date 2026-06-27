import axios from "axios";

export const api = axios.create({ baseURL: "/api" });

let accessToken: string | null = localStorage.getItem("access_token");
let refreshToken: string | null = localStorage.getItem("refresh_token");

export function setTokens(access: string | null, refresh: string | null) {
  accessToken = access;
  refreshToken = refresh;
  if (access) localStorage.setItem("access_token", access);
  else localStorage.removeItem("access_token");
  if (refresh) localStorage.setItem("refresh_token", refresh);
  else localStorage.removeItem("refresh_token");
}

export function hasTokens(): boolean {
  return Boolean(accessToken);
}

api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  return config;
});

let refreshing: Promise<void> | null = null;

api.interceptors.response.use(undefined, async (error) => {
  const original = error.config;
  if (error.response?.status === 401 && refreshToken && !original._retried) {
    original._retried = true;
    refreshing ??= api
      .post("/auth/refresh", { refresh_token: refreshToken })
      .then(({ data }) => setTokens(data.access_token, data.refresh_token))
      .catch(() => {
        setTokens(null, null);
        window.location.href = "/login";
      })
      .finally(() => {
        refreshing = null;
      });
    await refreshing;
    return api(original);
  }
  throw error;
});

export function errorText(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((d) => d.msg).join("; ");
  }
  return "Сталася помилка. Спробуйте ще раз";
}

// --- Типи API ---

export type Role = "admin" | "grc_manager" | "executor" | "reader";

export interface UserBrief {
  id: number;
  email: string;
  full_name: string;
  role: Role;
}

export interface CustomRole {
  id: number;
  name: string;
  permissions: Record<string, string>;
}

export interface User extends UserBrief {
  is_active: boolean;
  totp_enabled: boolean;
  custom_role: { id: number; name: string } | null;
  created_at: string;
  permissions?: Record<string, string>;
}

export interface APIToken {
  id: number;
  name: string;
  user: UserBrief;
  token_prefix: string;
  created_at: string;
  expires_at: string | null;
  last_used_at: string | null;
}

export interface Category {
  id: number;
  name: string;
}

export type RiskStatus =
  | "draft"
  | "identified"
  | "assessed"
  | "in_treatment"
  | "monitored"
  | "closed";
export type TreatmentStrategy = "mitigate" | "accept" | "avoid" | "transfer";
export type ActionStatus = "open" | "in_progress" | "done" | "verified";
export type RiskLevel = "low" | "medium" | "high" | "critical";
export type ImplStatus = "not_implemented" | "partial" | "implemented" | "not_applicable";
export type ControlType = "preventive" | "detective" | "corrective";

export interface SystemBrief {
  id: number;
  code: string;
  name: string;
}

export type ImpactLevel = "low" | "moderate" | "high";

export interface System extends SystemBrief {
  description: string | null;
  owner: UserBrief | null;
  criticality: "low" | "medium" | "high" | "critical" | null;
  profile_type: "confidential" | "service" | "registry" | null;
  impact_confidentiality: ImpactLevel | null;
  impact_integrity: ImpactLevel | null;
  impact_availability: ImpactLevel | null;
  status: "operational" | "development" | "decommissioned";
  created_at: string;
}

export type BaselineLevel =
  | "low"
  | "moderate"
  | "high"
  | "nd_confidential"
  | "nd_service"
  | "custom";

export interface Baseline {
  id: number;
  catalog_id: number;
  name: string;
  level: BaselineLevel;
  description: string | null;
  created_at: string;
  item_count: number;
}

export interface BaselineDetail extends Baseline {
  items: RequirementBrief[];
}

export interface Categorization {
  system_id: number;
  impact_confidentiality: ImpactLevel | null;
  impact_integrity: ImpactLevel | null;
  impact_availability: ImpactLevel | null;
  profile_type: "confidential" | "service" | null;
  overall_impact: ImpactLevel | null;
  suggested_baseline_id: number | null;
  suggested_baseline_name: string | null;
}

// --- Профілі / tailoring (RMF, ТЗ §5) ---

export type ProfileStatus = "draft" | "approved" | "superseded";
export type ControlOrigin = "baseline" | "added";
export type TailoringAction = "add" | "remove" | "modify_param";

export interface ProfileControl {
  id: number;
  requirement: RequirementBrief;
  included: boolean;
  origin: ControlOrigin;
}

export interface TailoringDecision {
  id: number;
  action: TailoringAction;
  requirement_id: number | null;
  parameter_id: number | null;
  value: string | null;
  justification: string;
  created_by: UserBrief | null;
  created_at: string;
}

export interface Profile {
  id: number;
  system_id: number;
  baseline_id: number | null;
  parent_profile_id: number | null;
  name: string;
  version: number;
  status: ProfileStatus;
  created_at: string;
  approved_at: string | null;
  control_count: number;
}

export interface ProfileDetail extends Profile {
  controls: ProfileControl[];
  decisions: TailoringDecision[];
}

export interface ResolvedParameter {
  parameter_id: number;
  key: string;
  label: string | null;
  value: string | null;
  org_defined: boolean;
  needs_input: boolean;
}

export interface ResolvedControl {
  requirement_id: number;
  code: string;
  title: string;
  description: string | null;
  origin: ControlOrigin;
  parameters: ResolvedParameter[];
}

export interface ResolvedProfile {
  profile_id: number;
  system_id: number;
  name: string;
  version: number;
  status: ProfileStatus;
  control_count: number;
  controls: ResolvedControl[];
}

// --- SSP (план безпеки системи, ТЗ §6) ---

export type SSPStatus = "draft" | "approved" | "superseded";

export interface SSPControl {
  id: number;
  requirement: RequirementBrief;
  implementation_status: ImplStatus;
  narrative: string | null;
  responsible: UserBrief | null;
}

export interface SSP {
  id: number;
  system_id: number;
  profile_id: number | null;
  parent_ssp_id: number | null;
  title: string;
  version: number;
  status: SSPStatus;
  system_description: string | null;
  created_at: string;
  approved_at: string | null;
  control_count: number;
  implemented_count: number;
}

export interface SSPDetail extends SSP {
  controls: SSPControl[];
}

// --- POA&M (план дій та контрольних точок, ТЗ §6) ---

export type POAMStatus = "open" | "in_progress" | "completed" | "risk_accepted";
export type Severity4 = "low" | "medium" | "high" | "critical";

export interface POAMMilestone {
  id: number;
  title: string;
  due_date: string | null;
  completed: boolean;
  completed_at: string | null;
  created_at: string;
}

export interface POAMItem {
  id: number;
  system_id: number;
  requirement: RequirementBrief | null;
  title: string;
  weakness: string | null;
  status: POAMStatus;
  severity: Severity4 | null;
  source: "manual" | "from_gap" | "from_finding";
  responsible: UserBrief | null;
  due_date: string | null;
  created_at: string;
  milestone_count: number;
  milestone_done: number;
}

export interface POAMItemDetail extends POAMItem {
  milestones: POAMMilestone[];
}

export interface POAMFromProfile {
  created: number;
  skipped: number;
  items: POAMItem[];
}

// --- Оцінювання (800-53A) + ConMon (ТЗ §7) ---

export type AssessmentStatus = "planned" | "in_progress" | "completed";
export type AssessmentResultValue = "not_assessed" | "satisfied" | "other_than_satisfied";

export interface AssessmentResult {
  id: number;
  requirement: RequirementBrief;
  result: AssessmentResultValue;
  notes: string | null;
  assessed_at: string | null;
}

export interface Assessment {
  id: number;
  system_id: number;
  profile_id: number | null;
  title: string;
  status: AssessmentStatus;
  assessor: UserBrief | null;
  created_at: string;
  completed_at: string | null;
  total: number;
  satisfied: number;
  other_than_satisfied: number;
  not_assessed: number;
}

export interface AssessmentDetail extends Assessment {
  results: AssessmentResult[];
}

export interface ConMonControl {
  requirement_id: number;
  code: string;
  title: string;
  state: string;
  evidence_count: number;
  latest_valid_until: string | null;
}

export interface ConMonHealth {
  system_id: number;
  profile_id: number | null;
  total: number;
  fresh: number;
  stale: number;
  none: number;
  drift: ConMonControl[];
}

// --- Авторозрахунок ризику (ТЗ §8) ---

export interface RiskControlEffectiveness {
  code: string;
  name: string;
  status: string | null;
  effectiveness: number | null;
}

export interface ResidualPreview {
  effectiveness: number;
  inherent_likelihood: number | null;
  inherent_impact: number | null;
  computed_residual_likelihood: number | null;
  computed_residual_impact: number | null;
  current_residual_likelihood: number | null;
  current_residual_impact: number | null;
  applied: boolean;
  controls: RiskControlEffectiveness[];
}

export interface ControlBrief {
  id: number;
  code: string;
  name: string;
}

export interface GapControl {
  id: number;
  code: string;
  name: string;
  status: ImplStatus | null;
}

export interface RiskBrief {
  id: number;
  code: string;
  title: string;
  status: RiskStatus;
  category: Category | null;
  owner: UserBrief | null;
  next_review_date: string | null;
  inherent_likelihood: number | null;
  inherent_impact: number | null;
  residual_likelihood: number | null;
  residual_impact: number | null;
  treatment_strategy: TreatmentStrategy | null;
  systems: SystemBrief[];
  inherent_score: number | null;
  residual_score: number | null;
  residual_level: RiskLevel | null;
}

export interface Assessment {
  id: number;
  kind: "inherent" | "residual";
  likelihood: number;
  impact: number;
  assessed_by: UserBrief | null;
  assessed_at: string;
}

export interface TreatmentAction {
  id: number;
  title: string;
  assignee: UserBrief | null;
  deadline: string | null;
  status: ActionStatus;
  created_at: string;
}

export interface Risk extends RiskBrief {
  description: string | null;
  assets: string | null;
  threat_source: string | null;
  vulnerability: string | null;
  acceptance_comment: string | null;
  accepted_by: UserBrief | null;
  accepted_at: string | null;
  controls: ControlBrief[];
  assessments: Assessment[];
  actions: TreatmentAction[];
}

export interface Framework {
  id: number;
  code: string;
  name: string;
  version: string | null;
  is_custom: boolean;
}

export interface Requirement {
  id: number;
  code: string;
  title: string;
  description: string | null;
  profiles: string[];
}

export interface RequirementBrief {
  id: number;
  code: string;
  title: string;
  framework_id: number;
}

export interface Evidence {
  id: number;
  kind: "file" | "link";
  name: string;
  url: string | null;
  valid_until: string | null;
  uploaded_by: UserBrief | null;
  created_at: string;
}

export interface ControlListItem {
  id: number;
  code: string;
  name: string;
  control_type: ControlType | null;
  owner: UserBrief | null;
  aggregate_status: ImplStatus;
  systems: SystemBrief[];
  next_review_date: string | null;
  requirements: RequirementBrief[];
}

export interface Implementation {
  id: number;
  system: SystemBrief | null;
  implementation_status: ImplStatus;
  na_justification: string | null;
  review_period_months: number | null;
  next_review_date: string | null;
  evidence: Evidence[];
}

export interface Control {
  id: number;
  code: string;
  name: string;
  description: string | null;
  control_type: ControlType | null;
  owner: UserBrief | null;
  requirements: RequirementBrief[];
  implementations: Implementation[];
  aggregate_status: ImplStatus;
  created_at: string;
  updated_at: string;
}

export interface GapRow {
  requirement: Requirement;
  controls: GapControl[];
  coverage: "covered" | "partial" | "not_covered" | "not_applicable";
}

export interface GapSummary {
  framework: Framework;
  total: number;
  covered: number;
  partial: number;
  not_covered: number;
  not_applicable: number;
  coverage_percent: number;
  requirements: GapRow[];
}

export interface Dashboard {
  risks_total: number;
  risks_by_status: Record<string, number>;
  risks_by_level: Record<string, number>;
  heat_map: { likelihood: number; impact: number; count: number }[];
  top_risks: RiskBrief[];
  overdue_risk_reviews: number;
  overdue_control_reviews: number;
  overdue_actions: number;
  overdue_policy_reviews: number;
  frameworks: { framework: Framework; coverage_percent: number; covered: number; total: number }[];
}

export interface AuditEntry {
  id: number;
  user: UserBrief | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface Comment {
  id: number;
  author: UserBrief | null;
  text: string;
  created_at: string;
}

// --- Типи Фази 2 ---

export type AuditStatus = "planned" | "in_progress" | "reporting" | "closed";
export type AuditType = "internal" | "external";
export type ChecklistResult = "compliant" | "partial" | "non_compliant" | "not_applicable";
export type Severity = "low" | "medium" | "high" | "critical";
export type PolicyStatus = "draft" | "approval" | "approved" | "active" | "review" | "archived";
export type Decision = "pending" | "approved" | "rejected";

export interface ChecklistItem {
  id: number;
  requirement_id: number | null;
  text: string;
  result: ChecklistResult | null;
  comment: string | null;
}

export interface Finding {
  id: number;
  code: string;
  title: string;
  description: string | null;
  severity: Severity;
  control: ControlBrief | null;
  requirement_id: number | null;
  risk: { id: number; code: string; title: string } | null;
  action_title: string | null;
  responsible: UserBrief | null;
  deadline: string | null;
  action_status: ActionStatus;
  created_at: string;
}

export interface AuditBrief {
  id: number;
  code: string;
  title: string;
  audit_type: AuditType;
  status: AuditStatus;
  systems: SystemBrief[];
  framework: Framework | null;
  date_from: string | null;
  date_to: string | null;
  auditor: UserBrief | null;
  auditor_external: string | null;
}

export interface Audit extends AuditBrief {
  scope: string | null;
  checklist: ChecklistItem[];
  findings: Finding[];
  created_at: string;
}

export interface Approval {
  id: number;
  approver: UserBrief;
  decision: Decision;
  comment: string | null;
  decided_at: string | null;
}

export interface Ack {
  id: number;
  user: UserBrief;
  assigned_at: string;
  acknowledged_at: string | null;
}

export interface PolicyVersion {
  id: number;
  number: number;
  content_md: string | null;
  file_name: string | null;
  created_by: UserBrief | null;
  created_at: string;
  approved_at: string | null;
  activated_at: string | null;
  approvals: Approval[];
  acks: Ack[];
}

export interface PolicyListItem {
  id: number;
  code: string;
  title: string;
  status: PolicyStatus;
  systems: SystemBrief[];
  owner: UserBrief | null;
  next_review_date: string | null;
  version_number: number | null;
  ack_total: number;
  ack_done: number;
  pending_my_approval: boolean;
  pending_my_ack: boolean;
}

export interface Policy {
  id: number;
  code: string;
  title: string;
  status: PolicyStatus;
  owner: UserBrief | null;
  next_review_date: string | null;
  systems: SystemBrief[];
  controls: ControlBrief[];
  versions: {
    id: number;
    number: number;
    file_name: string | null;
    created_at: string;
    approved_at: string | null;
    activated_at: string | null;
  }[];
  current_version: PolicyVersion | null;
  created_at: string;
}

export interface MyTask {
  kind: string;
  title: string;
  entity_type: string;
  entity_id: number;
  entity_code: string;
  due_date: string | null;
  overdue: boolean;
}

export interface ImportReport {
  total_rows: number;
  valid_rows: number;
  errors: { row: number; message: string }[];
  created: number;
  dry_run: boolean;
}

export interface AiCitation {
  source_type: string;
  source_id: number;
  score: number;
}

export interface AiAnswer {
  answer: string;
  citations: AiCitation[];
  suggestion_id: number;
}

export interface AiDraft {
  draft: string;
  citations: AiCitation[];
  suggestion_id: number;
}

export interface AiControlSuggestion {
  requirement_id: number;
  code: string;
  title: string;
  framework_id: number;
  score: number;
}

export interface AiControlSuggestions {
  suggestions: AiControlSuggestion[];
  rationale: string;
  suggestion_id: number;
}

export interface AgentRunStep {
  step: string;
  status: string;
  [k: string]: unknown;
}

export interface AgentBootstrapResult {
  system_id: number;
  profile_id: number;
  ssp_id: number;
  narratives_drafted: number;
  poam_created: number;
  steps: AgentRunStep[];
  summary: string;
  suggestion_id: number;
}
