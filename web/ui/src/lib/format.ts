export function fmtMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

export function fmtQuality(q: number | null | undefined): string {
  if (q === null || q === undefined) return "—";
  return q.toFixed(4);
}

export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleTimeString();
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString();
}

export function shortId(id: string): string {
  return id.slice(0, 8);
}

export function statusClass(s: string): "good" | "bad" | "warn" {
  if (s === "succeeded") return "good";
  if (s === "failed") return "bad";
  return "warn";
}
