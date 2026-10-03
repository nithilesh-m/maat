export type Role = "viewer" | "reviewer" | "admin";
export type GateOutcome = "pass" | "waive" | "block" | "fail" | "abstain" | "not_applicable";
export type RunStatus = "queued" | "running" | "paused" | "complete" | "failed";

export interface RunRow {
  run_id: string;
  run_dir: string;
  profile: string;
  planner: string;
  created_by: string;
  created_at: string;
  status: RunStatus;
  error: string | null;
  bundle_id?: string | null;
  pending_approval?: Record<string, unknown> | null;
  replay?: { matched: boolean; message: string } | null;
}
export interface JudgeVote {
  model: string;
  label: "S" | "P" | "N" | "NA" | "invalid";
  confidence: number;
  cited: string[];
}
export interface GateDecision {
  clause_id: string;
  gate: string;
  method: "rego" | "judge_panel" | "human" | "none";
  policy_version: string;
  inputs: string[];
  outcome: GateOutcome;
  rationale: string;
  partial: boolean;
  judges: JudgeVote[];
  agreement: number | null;
  waiver_id: string | null;
}
export interface Finding {
  id: string;
  agent: string;
  clause_ids: string[];
  severity: "low" | "medium" | "high" | "critical";
  claim: string;
  evidence_ids: string[];
  status: "proposed" | "confirmed" | "disputed" | "insufficient_evidence";
  dispute_reason: string | null;
}
export interface ArtifactRef {
  uri: string;
  sha256: string;
  sensitive: boolean;
}
export interface EvidenceRecord {
  id: string;
  seq: number;
  run_id: string;
  agent: string;
  tool: string;
  evidence_type: string;
  target_ref: string;
  params: Record<string, unknown>;
  result: {
    metrics?: Record<string, number | string>;
    samples?: unknown[];
    error?: string;
    [k: string]: unknown;
  };
  artifacts: ArtifactRef[];
  started_at: string;
  ended_at: string;
  prev_hash: string;
  hash: string;
  signer: string;
  sig: string;
}
export interface EvidenceLink {
  record_id: string;
  hash: string;
}
export interface ClauseRow {
  regime: string;
  regime_clause: string;
  control_id: string;
  adequacy: number;
  outcome: GateOutcome;
  evidence: EvidenceLink[];
  waiver_id: string | null;
}
export interface RegimeView {
  rows: ClauseRow[];
  cc: number;
  as: number;
  mer: number;
}
export interface Scores {
  regimes: Record<string, { cc: number; as: number; mer: number }>;
  dimensions: Record<string, number>;
}
export interface VerifyReport {
  ok: boolean;
  problems: string[];
  bundle_id: string | null;
  records: number;
}
export interface MitigationPlan {
  control_id: string;
  mitigation_id: string;
  rationale: string;
  severity_score: number;
}
export interface DeltaRow {
  control_id: string;
  regime_clause: string;
  before_outcome: GateOutcome | null;
  after_outcome: GateOutcome;
  before_a: number | null;
  after_a: number;
}
export interface MaatEvent {
  seq: number;
  kind: string;
  payload: Record<string, unknown>;
}
