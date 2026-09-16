export type Severity = "error" | "warning" | "info";

export interface Finding {
  rule_id: string;
  severity: Severity;
  element: string | null;
  message: string;
  detail: string;
}

export interface Counts {
  error: number;
  warning: number;
  info: number;
}

export interface ValidateResponse {
  mod_name: string;
  element_count: number;
  variable_count: number;
  texture_count: number;
  findings: Finding[];
  counts: Counts;
}
