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

export interface User extends UserBrief {
  is_active: boolean;
  totp_enabled: boolean;
  created_at: string;
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

export interface ControlBrief {
  id: number;
  code: string;
  name: string;
  implementation_status: ImplStatus;
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
  implementation_status: ImplStatus;
  next_review_date: string | null;
  requirements: RequirementBrief[];
}

export interface Control extends ControlListItem {
  description: string | null;
  na_justification: string | null;
  review_period_months: number | null;
  evidence: Evidence[];
}

export interface GapRow {
  requirement: Requirement;
  controls: ControlBrief[];
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
