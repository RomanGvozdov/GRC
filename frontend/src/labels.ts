import type {
  ActionStatus,
  ControlType,
  ImplStatus,
  RiskLevel,
  RiskStatus,
  Role,
  TreatmentStrategy,
} from "./api";

export const ROLE_LABELS: Record<Role, string> = {
  admin: "Адміністратор",
  grc_manager: "GRC-менеджер",
  executor: "Виконавець",
  reader: "Читач",
};

export const RISK_STATUS_LABELS: Record<RiskStatus, string> = {
  draft: "Чернетка",
  identified: "Ідентифікований",
  assessed: "Оцінений",
  in_treatment: "В обробці",
  monitored: "Моніториться",
  closed: "Закритий",
};

export const STRATEGY_LABELS: Record<TreatmentStrategy, string> = {
  mitigate: "Зменшити",
  accept: "Прийняти",
  avoid: "Уникнути",
  transfer: "Передати",
};

export const ACTION_STATUS_LABELS: Record<ActionStatus, string> = {
  open: "Відкрита",
  in_progress: "В роботі",
  done: "Виконана",
  verified: "Перевірена",
};

export const LEVEL_LABELS: Record<RiskLevel, string> = {
  low: "Низький",
  medium: "Середній",
  high: "Високий",
  critical: "Критичний",
};

export const LEVEL_COLORS: Record<RiskLevel, string> = {
  low: "green",
  medium: "yellow",
  high: "orange",
  critical: "red",
};

export const IMPL_LABELS: Record<ImplStatus, string> = {
  not_implemented: "Не впроваджено",
  partial: "Частково",
  implemented: "Впроваджено",
  not_applicable: "Не застосовно",
};

export const IMPL_COLORS: Record<ImplStatus, string> = {
  not_implemented: "red",
  partial: "yellow",
  implemented: "green",
  not_applicable: "gray",
};

export const CONTROL_TYPE_LABELS: Record<ControlType, string> = {
  preventive: "Превентивний",
  detective: "Детективний",
  corrective: "Коригувальний",
};

export const COVERAGE_LABELS: Record<string, string> = {
  covered: "Покрито",
  partial: "Частково",
  not_covered: "Не покрито",
  not_applicable: "Не застосовно",
};

export const COVERAGE_COLORS: Record<string, string> = {
  covered: "green",
  partial: "yellow",
  not_covered: "red",
  not_applicable: "gray",
};

export function scoreLevel(score: number | null): RiskLevel | null {
  if (score === null) return null;
  if (score <= 4) return "low";
  if (score <= 9) return "medium";
  if (score <= 14) return "high";
  return "critical";
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  return d.toLocaleDateString("uk-UA", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export function formatDateTime(value: string): string {
  const d = new Date(value + (value.endsWith("Z") ? "" : "Z"));
  return d.toLocaleString("uk-UA", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function toOptions(labels: Record<string, string>) {
  return Object.entries(labels).map(([value, label]) => ({ value, label }));
}

export const AUDIT_STATUS_LABELS: Record<string, string> = {
  planned: "Запланований",
  in_progress: "Триває",
  reporting: "Звіт",
  closed: "Закритий",
};

export const AUDIT_TYPE_LABELS: Record<string, string> = {
  internal: "Внутрішній",
  external: "Зовнішній",
};

export const RESULT_LABELS: Record<string, string> = {
  compliant: "Відповідає",
  partial: "Частково",
  non_compliant: "Не відповідає",
  not_applicable: "Не застосовно",
};

export const RESULT_COLORS: Record<string, string> = {
  compliant: "green",
  partial: "yellow",
  non_compliant: "red",
  not_applicable: "gray",
};

export const SEVERITY_LABELS: Record<string, string> = {
  low: "Низька",
  medium: "Середня",
  high: "Висока",
  critical: "Критична",
};

export const SEVERITY_COLORS: Record<string, string> = {
  low: "green",
  medium: "yellow",
  high: "orange",
  critical: "red",
};

export const POLICY_STATUS_LABELS: Record<string, string> = {
  draft: "Чернетка",
  approval: "На погодженні",
  approved: "Затверджена",
  active: "Діюча",
  review: "Переглядається",
  archived: "Архівна",
};

export const POLICY_STATUS_COLORS: Record<string, string> = {
  draft: "gray",
  approval: "yellow",
  approved: "teal",
  active: "green",
  review: "orange",
  archived: "dark",
};

export function downloadBlob(data: Blob, filename: string) {
  const url = URL.createObjectURL(data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export const PROFILE_LABELS: Record<string, string> = {
  confidential: "Конфіденційна інформація",
  service: "Службова інформація (ДСК)",
  registry: "Публічні електронні реєстри",
};

export const PROFILE_SHORT: Record<string, string> = {
  confidential: "К",
  service: "С",
  registry: "Р",
};
