import type { BackendInfo, LerCurve, RunDetail, RunSummary } from "./types";

const API_BASE = "";  // same-origin in prod; rewritten by next.config.ts in dev

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path}: ${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export async function fetchHealth(): Promise<{ status: string; postgres: { db: string; user: string } }> {
  return getJSON("/api/health");
}

export async function fetchRuns(limit = 50, skill?: string): Promise<{ count: number; runs: RunSummary[] }> {
  const q = new URLSearchParams({ limit: String(limit) });
  if (skill) q.set("skill", skill);
  return getJSON(`/api/runs?${q}`);
}

export async function fetchRun(runId: string): Promise<RunDetail> {
  return getJSON(`/api/runs/${runId}`);
}

export async function fetchBackends(): Promise<{ count: number; backends: BackendInfo[] }> {
  return getJSON("/api/backends");
}

export async function fetchQecLerCurve(opts?: {
  distance?: number;
  rounds?: number;
  basis?: string;
}): Promise<LerCurve> {
  const q = new URLSearchParams();
  if (opts?.distance !== undefined) q.set("distance", String(opts.distance));
  if (opts?.rounds !== undefined) q.set("rounds", String(opts.rounds));
  if (opts?.basis) q.set("basis", opts.basis);
  const suffix = q.toString() ? `?${q}` : "";
  return getJSON(`/api/qec/ler-curve${suffix}`);
}
