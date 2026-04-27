"use client";

import { useMemo } from "react";
import { fmtMs, fmtQuality } from "@/lib/format";
import type { DispatchRow, ProblemRow } from "@/lib/types";
import styles from "./BackendBakeoff.module.css";

interface Props {
  problem: ProblemRow;
  dispatches: DispatchRow[];
}

export default function BackendBakeoff({ problem, dispatches }: Props) {
  // Sort: winner first, then losers by quality desc.
  const sorted = useMemo(() => {
    const xs = [...dispatches];
    xs.sort((a, b) => {
      if (a.is_winner !== b.is_winner) return a.is_winner ? -1 : 1;
      return (b.quality ?? 0) - (a.quality ?? 0);
    });
    return xs;
  }, [dispatches]);

  const maxWall = useMemo(
    () => Math.max(1, ...dispatches.map((d) => d.wall_time_ms ?? 0)),
    [dispatches],
  );

  const metricColLabel =
    problem.problem_class === "qec_syndrome" ? "LER"
      : problem.problem_class === "qubo_assignment" ? "Objective"
        : "Note";

  return (
    <div className={styles.panel}>
      <h2>
        Backend bake-off · {dispatches.length} participant{dispatches.length === 1 ? "" : "s"}
      </h2>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Backend</th>
            <th>Substrate</th>
            <th>Quality</th>
            <th>Wall time</th>
            <th>{metricColLabel}</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((d) => (
            <DispatchRowComponent
              key={d.dispatch_id}
              d={d}
              problem={problem}
              maxWall={maxWall}
            />
          ))}
        </tbody>
      </table>
      <footer className={styles.footer}>
        Race history is recorded in <code>common.dispatches</code> + <code>common.outcomes</code>.
        Winner is max quality, ties broken by lowest wall time.
      </footer>
    </div>
  );
}

function DispatchRowComponent({
  d,
  problem,
  maxWall,
}: {
  d: DispatchRow;
  problem: ProblemRow;
  maxWall: number;
}) {
  const m = (d.metric_payload ?? {}) as Record<string, unknown>;
  const failed = m.success === false;
  const cls = `${styles.row}${d.is_winner ? ` ${styles.winner}` : ""}${failed ? ` ${styles.failed}` : ""}`;

  const q = d.quality ?? 0;
  const qBarCls = q > 0.95 ? "" : q > 0.5 ? styles.warn : styles.bad;
  const qBarWidth = Math.max(0, Math.min(1, q)) * 120;
  const wallBarWidth = Math.max(0, (d.wall_time_ms ?? 0) / maxWall) * 120;

  let gpuPill: React.ReactNode;
  if (d.gpu_lane === null || d.gpu_lane === undefined) {
    gpuPill = <span className="gpu-pill">CPU</span>;
  } else {
    gpuPill = <span className={`gpu-pill gpu${d.gpu_lane}`}>GPU {d.gpu_lane}</span>;
  }

  let metricCell: React.ReactNode = "";
  if (problem.problem_class === "qec_syndrome" && typeof m.ler === "number") {
    metricCell = m.ler.toFixed(4);
  } else if (problem.problem_class === "qubo_assignment" && m.objective != null) {
    const infeasible = m.is_feasible === false ? " (infeasible)" : "";
    metricCell = `${m.objective}${infeasible}`;
  } else if (typeof m.error === "string") {
    metricCell = <span className={styles.errorMessage}>{m.error.slice(0, 60)}</span>;
  }

  return (
    <tr className={cls}>
      <td>
        {d.backend_name}
        {d.is_winner && (
          <>
            {" "}
            <span className="pill good">winner</span>
          </>
        )}
      </td>
      <td>{gpuPill}</td>
      <td>
        <span className={styles.barTrack}>
          <span className={`${styles.bar} ${qBarCls}`} style={{ width: qBarWidth }} />
        </span>
        <span className={styles.numeric}>{fmtQuality(d.quality)}</span>
      </td>
      <td>
        <span className={styles.barTrack}>
          <span className={`${styles.bar} ${styles.dim}`} style={{ width: wallBarWidth }} />
        </span>
        <span className={styles.numeric}>{fmtMs(d.wall_time_ms)}</span>
      </td>
      <td>{metricCell}</td>
    </tr>
  );
}
