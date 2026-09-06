export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8799";

export type VerdictName =
  | "CONFIRMED"
  | "CONTRADICTED"
  | "UNRESOLVED"
  | "NO_AUTHORITY";

export type RuleStep = {
  index: number;
  rule: string;
  status: "passed" | "failed" | "not_reached";
  detail: string;
  /** The rule that actually produced the verdict. */
  decided: boolean;
};

/** One turn of the call, with its body pre-cut against the confirmed quote
 *  spans so the highlight is the adjudicator's range, not a re-search. */
export type TranscriptLine = {
  speaker: string;
  text: string;
  offset_seconds: number | null;
  start: number;
  end: number;
  segments: { text: string; field: string | null }[];
};

export type LedgerRow = {
  field: string;
  verdict: VerdictName;
  reason: string;
  reason_text: string;
  value: string;
  raw_value: string;
  quote: string;
  quote_start: number;
  quote_end: number;
  source: string;
  respondent_role: string;
  rule: number;
  known_value: string;
  rule_trace: RuleStep[];
  rejected_span: RejectedSpan | null;
  seq?: number;
  call_id?: string;
  subject_id?: string;
  schema_name?: string;
  created_at?: string;
};

export type RejectedSpan = {
  field: string;
  claimed_quote: string;
  claimed_value: string;
  source: string;
  detail: string;
};

export type Meta = {
  project: string;
  tagline: string;
  schemas: string[];
  call_budget: number;
  calls_used: number;
  calls_remaining: number;
  live_call_floor: number;
  verdict_count: number;
  screen_count: number;
  rule_count: number;
  max_attempts: number;
};

export type Subject = {
  id: string;
  label: string;
  contact_name: string;
  contact_org: string;
  known_values: Record<string, string>;
};

export type LedgerGroup = {
  subject_id: string;
  label: string;
  contact_name: string;
  contact_org: string;
  known_values: Record<string, string>;
  rows: LedgerRow[];
  counts: Record<VerdictName, number>;
  urgency: number;
  open_count: number;
};

export type LedgerResponse = {
  schema: string | null;
  subjects: Subject[];
  rows: LedgerRow[];
  groups: LedgerGroup[];
  history: LedgerRow[];
  counts: Record<VerdictName, number>;
};

export type CallSummary = {
  id: string;
  subject_id: string;
  schema_name: string;
  attempt: number;
  mode: string;
  asked_fields: string[];
  duration_seconds: number;
  end_reason: string;
  respondent_role: string;
  created_at: string;
};

export type CallDetail = {
  call: CallSummary & {
    transcript: string;
    turns: { speaker: string; text: string; offset_seconds: number | null }[];
    task: string;
    structured_result: Record<string, unknown>;
  };
  lines: TranscriptLine[];
  rows: LedgerRow[];
  counts: Record<VerdictName, number>;
  rejected_spans: RejectedSpan[];
};

export type RequeueCard = {
  subject_id: string;
  schema_name: string;
  label: string;
  open: {
    field: string;
    state: string;
    attempts: number;
    reason: string;
    verdict: VerdictName;
    needs_different_respondent: number;
  }[];
  dropped_from_goal: { field: string; verdict: VerdictName; value: string }[];
  next_goal: string;
  next_fields: string[];
  attempts: number;
  max_attempts: number;
  actionable: boolean;
  needs_different_respondent: boolean;
};

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${path} responded ${response.status}`);
  }
  return (await response.json()) as T;
}

export const getMeta = () => get<Meta>("/api/meta");
export const getLedger = (schema?: string) =>
  get<LedgerResponse>(`/api/ledger${schema ? `?schema=${schema}` : ""}`);
export const getCalls = (subject?: string) =>
  get<CallSummary[]>(`/api/calls${subject ? `?subject=${subject}` : ""}`);
export const getCall = (id: string) =>
  get<CallDetail>(`/api/calls/${encodeURIComponent(id)}`);
export const getRequeue = (schema?: string) =>
  get<RequeueCard[]>(`/api/requeue${schema ? `?schema=${schema}` : ""}`);

export async function runRequeue(subjectId: string, schemaName: string) {
  const response = await fetch(`${API_BASE}/api/requeue/run`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ subject_id: subjectId, schema_name: schemaName }),
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.detail ?? `request failed (${response.status})`);
  }
  return body;
}
