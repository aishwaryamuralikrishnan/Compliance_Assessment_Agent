// The shapes of the API contract (docs/web_app_design.md §3 and §5). Free-form JSON from the database (assessments,
// rows) stays loosely typed on purpose: the pages show what the graph produced.

export type Role = "product_manager" | "dpo";

export interface User {
  user_id: string;
  role: Role;
  display_name: string;
}

export interface Finding {
  severity: "Blocker" | "Required" | "Covered";
  text: string;
  citations: string[];
}

export interface ChangeNote {
  request: string;
  pm_response: string;
  outcome: "closed" | "narrowed" | "kept" | "new";
  finding: string;
  explanation: string;
}

export interface Assessment {
  assessment_id?: string;
  title: string;
  verdict: "Do not build as described" | "Proceed with conditions" | "Proceed";
  risk_level: "low" | "medium" | "high";
  summary: string;
  high_risk_ai: boolean;
  dpia_required: boolean;
  findings: Finding[];
  next_steps: string[];
  revises?: string | null;
  changes_since_v1?: ChangeNote[] | null;
  sources?: string[];
  verified_citations?: string[];
  unverified_citations?: string[];
  disclaimer?: string;
  revision_rule_violation?: string;
}

// --- the live graph: the tracker's snapshot and the layout --------------------------------------

export interface GraphSnapshot {
  active: string | null;
  visited: string[];
  taken: [string, string][];
  paused: boolean;
  pm_paused: boolean;
  resumed: boolean;
  substep: string | null;
  substeps_done: string[];
  rewrote: boolean;
  da_state: "on" | "done" | null;
  gate_state: string | null;
  finished: boolean;
  retrievals: number;
  tool_calls: number;
  tokens_in: number;
  tokens_out: number;
  tokens_cached: number;
  cost: number;
}

export interface LayoutNode {
  kind: "circle" | "rect" | "diamond" | "worker" | "direct";
  cx?: number;
  cy?: number;
  r?: number;
  x?: number;
  y?: number;
  w?: number;
  h?: number;
  label: string | string[];
  lpos?: "left" | "below";
  small?: boolean;
  small2?: boolean;
}

export interface LayoutEdge {
  source: string;
  target: string;
  points: [number, number][];
  style: "solid" | "dashed";
}

export interface GraphLayout {
  viewbox: [number, number, number, number];
  nodes: Record<string, LayoutNode>;
  substeps: Record<string, [number, number, number, number]>;
  substep_edges: LayoutEdge[];
  substep_labels: [string, number, number, string][];
  da_substep: [number, number, number, number];
  edges: LayoutEdge[];
}

// --- the stream ------------------------------------------------------------------------------------

export interface RunStats {
  step: string;
  searches: number;
  retrieve_passes: number;
  rewrites: number;
  tool_calls: number;
  tokens_in: number;
  tokens_out: number;
  cached: number;
  cost: number;
  elapsed: number;
  thread: string;
}

export interface TraceRow {
  label: string;
  detail: string; // HTML snippet produced by the server (escaped there)
  attempt: number | null;
  tip: string;
}

export interface TraceSection {
  key: string;
  title: string;
  cls: "" | "tool";
  subtitle: string;
  items: string[]; // HTML snippets produced by the server (escaped there)
  rows: TraceRow[];
}

export interface View {
  seq?: number;
  title: string;
  graph: GraphSnapshot;
  stats: RunStats;
  trace: TraceSection[];
}

export interface PendingDpo {
  type: "dpo_review";
  task_id: number;
  assessment_id: string;
  title: string;
  requested_by: string;
  thread_id: string;
  assessment: Assessment;
}

export interface PendingPm {
  type: "pm_revision";
  thread_id: string;
  revises: string;
  title: string;
  requests: string[];
  comment: string;
  requested_by: string;
  requester: string;
  previous_description: string;
  error: string | null;
}

export interface ReviewTask {
  id: number;
  thread_id: string;
  assessment_id: string;
  title: string;
  requested_by: string;
  status: "pending" | "approved" | "changes_requested" | "rejected";
  dpo_comment: string | null;
  resolved_by: string | null;
  resolved_at: string | null;
  created_at: string;
}

export interface ThreadBody {
  thread_id: string;
  pending: { kind: "dpo" | "pm" | null; value: PendingDpo | PendingPm | null };
  running_run_id: string | null;
  run_in_progress: boolean;
  status: string | null;
  status_text: string | null;
  review_task: ReviewTask | null;
  values: {
    input?: string;
    validation?: Record<string, unknown>;
    route?: string;
    assessment?: Assessment | null;
    answer?: string | null;
    sources?: { citation?: string }[];
    guardrail?: Record<string, unknown>;
    decision?: string | null;
    revision?: Record<string, unknown> | null;
    revision_error?: string | null;
    feedback?: Record<string, unknown> | null;
  };
  last_view: View | null;
  views: RunView[]; // every run this API process executed on the thread, in start order
}

export interface RunView {
  run_id: string;
  kind: "turn" | "decision" | "revision" | "feedback";
  user_id: string;
  done: boolean;
  error: string | null;
  view: View;
}

export interface FinalEvent {
  thread: ThreadBody;
  run_id: string;
  graph_run_id: string;
  title: string;
}

export interface InterruptEvent {
  kind: "dpo" | "pm" | null;
  value: PendingDpo | PendingPm;
}

export interface Meta {
  models: Record<string, string>;
  model_ids: Record<string, string>;
  pricing: Record<string, Record<string, number>>;
  langsmith: { enabled: boolean; project: string };
}

export interface MemoryCandidate {
  item: { type: string; text: string; source: string; [k: string]: unknown };
  label: string;
  allowed: boolean;
}

export interface MemoryCandidatesOut {
  amendments: MemoryCandidate[];
  note: MemoryCandidate[];
  on_changes: MemoryCandidate[];
  on_reject: MemoryCandidate[];
}

export interface AssessmentRow {
  id: number;
  assessment_id: string;
  thread_id: string;
  title: string;
  assessment: Assessment;
  status: string;
  created_by: string;
  description: string | null;
  revises: string | null;
  version: number;
  created_at: string;
}

export interface ReviewDetail {
  task: ReviewTask;
  assessment: AssessmentRow;
  previous: AssessmentRow | null;
  requested_changes: string | null;
}

export interface RegisterEntry {
  assessment_id: string;
  title: string;
  verdict: string;
  risk_level: string;
  high_risk_ai: boolean;
  dpia_required: boolean;
  requested_by: string;
  approved_by: string;
  approved_at: string;
  revises: string | null;
  assessment: Assessment;
  history: HistoryEntry[];
}

export interface HistoryEntry {
  version: number;
  assessment_id: string;
  created_at: string;
  description: string | null;
  assessment: Assessment;
  decision: { status: string; resolved_by: string | null; dpo_comment: string | null } | null;
}

export interface MemoryItem {
  text: string;
  source?: string;
  author?: string;
  created_at?: string;
  assessment_id?: string;
  reflected?: boolean;
  detail?: string;
  [k: string]: unknown;
}

export interface MemoryOut {
  sections: { namespace: string; what: string; who: string; items: MemoryItem[]; error: string | null }[];
  can_add: string[];
}

// ---- the evaluation report (GET /api/eval/report; eval/harness/report.py) ----

export interface EvalMetric { key: string; label: string; definition: string; result: string; value: number | null; target: string | null; met: boolean | null; detail: string[] }
export interface EvalSet { id: string; name: string; what: string; data: string; judged: { rules: string | null; judge: string | null; human: string | null }; metrics: EvalMetric[]; run: boolean }
export interface EvalSection { id: string; title: string; sub: string; sets: EvalSet[] }
export interface EvalFlag { missed: number; positives: number; false: number; negatives: number }
/** The Legal domains tab: an area of the two regulations and the articles it rests on. */
export interface EvalDomain { id: string; name: string; law: "gdpr" | "ai" | "both"; articles: { text: string; law: "gdpr" | "ai" }[] }
export interface EvalPairHalf { id: string; text: string; expected: string; article: string; ok: boolean | null; why: string }
export interface EvalQuickHalf { e3_id: string; e5_id: string; text: string; article: string; e3: boolean | null; e5: boolean | null }
export interface EvalRouteHalf { id: string; text: string; route: string; ok: boolean | null }
export interface EvalPairs {
  full: { a: EvalPairHalf; b: EvalPairHalf; ok: boolean | null }[]; full_right: { right: number; of: number };
  quick: { a: EvalQuickHalf; b: EvalQuickHalf; e3: boolean | null; e5: boolean | null }[]; quick_e3: { right: number; of: number }; quick_e5: { right: number; of: number };
  routing: { a: EvalRouteHalf; b: EvalRouteHalf; ok: boolean | null }[]; routing_right: { right: number; of: number };
}
export interface EvalCase {
  id: string; domain: string | null; title: string | null;
  expected_verdict: string | null; verdict: string | null; verdict_ok: boolean; dangerous: boolean;
  risk_level: string | null; risk_ok: boolean;
  high_risk_ai: { got: boolean | null; expected: boolean | null }; dpia_required: { got: boolean | null; expected: boolean | null };
  key_findings: { matched: number | null; partial: number | null; missed: number | null; of: number | null; severity_miscalibrated: number };
  must_cite: { found: string[]; missing: string[] } | null; wrong_extras: number; faithfulness: number | null;
  cost: number; seconds: number | null; searches: number | null; rewrites: number | null;
}
export interface EvalReport {
  generated_at: string; results_dir: string; commit: string | null; models: Record<string, string> | null; database: string | null;
  run_date: string | null; judge_note: string | null;
  runs: Record<string, { folder: string; timestamp: string; cases: number | null }>; missing_sets: string[];
  sections: EvalSection[]; targets: EvalMetric[]; targets_met: number; targets_scored: number;
  e12: { route_accuracy: { right: number; of: number; wrong: string[] }; fallback: { count: number; of: number };
         detection: Record<"injection" | "pii_redacted" | "off_topic", { detected: number; of: number; missed: string[] }>;
         false_positives: { count: number; of: number; ids: string[] }; redactions_exact: { right: number; of: number };
         route_matrix: { order: string[]; counts: Record<string, Record<string, number>> };
         misrouted: { id: string; kind: string | null; expected: string | null; got: string | null; screen: string[]; text: string }[] } | null;
  e7: { caught: number; of: number; missed: string[]; faults: { id: string; fault: string | null; name: string | null; planted: string | null; expected: string | null; ok: boolean; why: string | null }[] } | null;
  e3: { recall_loop: { found: number; of: number }; recall_single: { found: number; of: number }; nice_recall_loop: { found: number; of: number };
        attempts_mean: number | null; rewrites_total: number; insufficient: string[]; loop_misses: string[]; single_misses: string[]; cost: number;
        gain: { queries: number; points: number; relative_pct: number | null; recovered: string[] };
        hard: { id: string; provision: string; domain: string | null; domain_name: string; recovered: boolean; text: string }[];
        grader: { tp: number; fp: number; fn: number; tn: number; grades: number; precision: number | null; recall: number | null; confidence_min_median_max?: number[] | null;
                  false_pass?: { id: string; confidence: number | null }[]; false_fail?: string[]; grades_logged?: number } } | null;
  e5: { quick_answers: { count: number; of: number; not_quick: string[] }; must_cite: { found: number; of: number; misses: string[] };
        invented: { count: number; rows: string[] }; faithfulness: { mean: number | null; over: number }; over_three_sentences: string[]; empty: string[]; cost: number;
        per_case: { id: string; quick: boolean; route?: string; must?: string[]; found?: string[]; missing?: string[]; faithfulness?: number | null; unsupported?: string[]; cost?: number }[] } | null;
  e6: { verdict_matrix: { order: string[]; counts: Record<string, Record<string, number>> };
        severity_matrix: { order: string[]; counts: Record<string, Record<string, number>>; note: string };
        key_findings: { matched: number; partial: number; severity_miscalibrated: number; of: number; missed: number; missed_absent: number };
        flags: Record<"high_risk_ai" | "dpia_required", EvalFlag>; verdict: { right: number; of: number; wrong: string[] }; dangerous_misses: string[];
        risk_level: { right: number; of: number }; must_cite: { found: number; of: number; misses: string[] }; wrong_extras: string[]; must_not_violations: string[];
        faithfulness: { mean: number | null; over: number }; pairs: { right: number; total: number; failed: string[] };
        run: { rewrites?: number; regenerations?: number; seconds_mean?: number | null }; cost: number | null; judge_cost: number | null;
        judge_vs_human: { agreed: number; of: number; unsure: string[]; disagreed: string[] } | null; per_case: EvalCase[] } | null;
  cost: { set: string; label: string; harness: number; gateway: number | null; cases: number | null }[];
  domains: EvalDomain[];
  pairs: EvalPairs;
  not_met: ({ set: string } & EvalMetric)[];
  notes: { title?: string; intro?: string; data_note?: string; shortfalls_intro?: string; headline?: string; summary?: string; judge_note?: string; failure_modes?: { title: string; text: string; example?: string; response?: string; response_kind?: string; cases?: string[] }[]; limitations?: string[]; next?: string[]; gateway_cost?: Record<string, number> };
}
