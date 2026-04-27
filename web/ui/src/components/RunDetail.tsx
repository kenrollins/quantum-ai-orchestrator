"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchRun } from "@/lib/api";
import { fmtMs, fmtTime, shortId } from "@/lib/format";
import type { DispatchRow, ProblemRow, RunDetail as RunDetailType } from "@/lib/types";
import AssignmentBipartite from "./AssignmentBipartite";
import BackendBakeoff from "./BackendBakeoff";
import QecCircuit from "./QecCircuit";
import QecLerCurve from "./QecLerCurve";
import styles from "./RunDetail.module.css";

interface Props {
  runId: string | null;
}

export default function RunDetail({ runId }: Props) {
  const [data, setData] = useState<RunDetailType | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!runId) {
      setData(null);
      setError(null);
      return;
    }
    setLoading(true);
    fetchRun(runId)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [runId]);

  if (!runId) {
    return <div className={styles.empty}>Pick a run from the left rail to inspect its race.</div>;
  }
  if (loading && !data) {
    return <div className={styles.empty}>Loading…</div>;
  }
  if (error) {
    return <div className={styles.empty}>Error loading run: {error}</div>;
  }
  if (!data) return null;

  return (
    <>
      <div className={styles.runHeader}>
        <h1>{data.run.ask_text}</h1>
        <div className={styles.metaRow}>
          <span>
            <strong>{data.run.skill || "?"}</strong>
          </span>
          <span>{data.run.status}</span>
          <span>wall {fmtMs(data.run.wall_time_ms)}</span>
          <span>started {fmtTime(data.run.started_at)}</span>
          <span className={styles.runId}>{shortId(data.run.run_id)}</span>
        </div>
      </div>

      {data.problems.map((p) => {
        const dispatches = data.dispatches.filter((d) => d.problem_id === p.problem_id);
        return <ProblemSection key={p.problem_id} problem={p} dispatches={dispatches} />;
      })}
    </>
  );
}

function ProblemSection({ problem, dispatches }: { problem: ProblemRow; dispatches: DispatchRow[] }) {
  const winner = useMemo(() => dispatches.find((d) => d.is_winner), [dispatches]);
  const summary = winner ? buildSummary(problem, winner) : null;

  const isQec = problem.problem_class === "qec_syndrome";
  const isAssignment = problem.problem_class === "qubo_assignment";
  const params = problem.params as Record<string, unknown>;
  const distance = params["distance"];
  const rounds = params["rounds"];
  const basis = params["basis"];

  return (
    <>
      <div className={styles.panel}>
        <h2>
          Problem {problem.problem_id} · {problem.problem_class}
        </h2>
        <div className={styles.paramsLine}>
          params: <code>{JSON.stringify(problem.params)}</code>
        </div>
        {summary}
      </div>

      <BackendBakeoff problem={problem} dispatches={dispatches} />

      {isQec && typeof distance === "number" && (
        <>
          <QecLerCurve distance={distance} />
          <QecCircuit
            distance={distance}
            rounds={typeof rounds === "number" ? rounds : 1}
            basis={typeof basis === "string" ? basis : "X"}
          />
        </>
      )}

      {isAssignment && <AssignmentBipartite problem={problem} dispatches={dispatches} />}
    </>
  );
}

function buildSummary(problem: ProblemRow, winner: DispatchRow): React.ReactNode {
  const m = (winner.metric_payload ?? {}) as Record<string, unknown>;
  const items: { label: string; value: React.ReactNode }[] = [];
  items.push({ label: "Winning backend", value: winner.backend_name });

  if (problem.problem_class === "qec_syndrome") {
    if (typeof m.ler === "number") items.push({ label: "LER", value: m.ler.toFixed(4) });
    const errs = typeof m.logical_errors === "number" ? m.logical_errors : "—";
    const shots = typeof m.shots === "number" ? m.shots : "—";
    items.push({ label: "Logical errors", value: `${errs} / ${shots}` });
  } else if (problem.problem_class === "qubo_assignment") {
    items.push({ label: "Objective", value: m.objective != null ? String(m.objective) : "—" });
    items.push({ label: "Feasible", value: m.is_feasible ? "yes" : "no" });
  }
  items.push({ label: "Wall time", value: fmtMs(winner.wall_time_ms) });

  return (
    <div className={styles.metricGrid}>
      {items.map((i) => (
        <div key={i.label} className={styles.metric}>
          <div className={styles.label}>{i.label}</div>
          <div className={styles.value}>{i.value}</div>
        </div>
      ))}
    </div>
  );
}
