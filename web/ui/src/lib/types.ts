// Types mirroring the FastAPI replay server response shapes
// (see web/api/serve_replay.py).

export type RunStatus = "pending" | "running" | "succeeded" | "failed";

export interface RunSummary {
  run_id: string;
  ask_text: string;
  skill: string;
  status: RunStatus;
  started_at: string;
  finished_at: string | null;
  wall_time_ms: number | null;
}

export interface ProblemRow {
  problem_id: string;
  parent_id: string | null;
  problem_class: string;
  params: Record<string, unknown>;
  created_at: string;
}

export interface DispatchRow {
  dispatch_id: string;
  problem_id: string;
  backend_name: string;
  gpu_lane: number | null;
  dispatched_at: string;
  quality: number | null;
  wall_time_ms: number | null;
  metric_payload: Record<string, unknown> | null;
  finished_at: string | null;
  is_winner: boolean;
}

export interface RunDetail {
  run: RunSummary;
  problems: ProblemRow[];
  dispatches: DispatchRow[];
}

export interface BackendInfo {
  name: string;
  class: string;
  applicable_problem_classes: string[];
  gpu_required: boolean;
  footprint_gb: number;
  latency_target_ms: number;
  phase: number;
}

export interface LerCurvePoint {
  noise_rate: number;
  // Backend names act as keys, e.g. point["pymatching"] = 0.0190.
  // Plus per-backend metadata: <backend>_run_id, _shots, _logical_errors, _wall_time_ms.
  [k: string]: number | string | null | undefined;
}

export interface LerCurve {
  filter: { distance: number | null; rounds: number | null; basis: string | null };
  series: string[];                  // backend names present in the data
  points: LerCurvePoint[];           // sorted by noise_rate ascending
  raw: Record<string, unknown>[];    // long-form rows for debug/export
}
