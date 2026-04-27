"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchRuns } from "@/lib/api";
import { fmtMs, fmtTime, statusClass } from "@/lib/format";
import type { RunSummary } from "@/lib/types";
import styles from "./RunList.module.css";

interface Props {
  selectedRunId: string | null;
  onSelect: (runId: string) => void;
}

export default function RunList({ selectedRunId, onSelect }: Props) {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchRuns(50);
      setRuns(data.runs);
      setError(null);
    } catch (e) {
      setError(String(e));
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5_000);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <>
      <div className={styles.sectionLabel}>Recent runs</div>
      {error && <div className={styles.empty}>Error: {error}</div>}
      {!error && runs.length === 0 && (
        <div className={styles.empty}>
          No runs yet. Use <code>qao run</code>.
        </div>
      )}
      {runs.map((r) => {
        const cls = `${styles.row}${r.run_id === selectedRunId ? ` ${styles.selected}` : ""}`;
        return (
          <div key={r.run_id} className={cls} onClick={() => onSelect(r.run_id)}>
            <div className={styles.ask}>{r.ask_text}</div>
            <div className={styles.meta}>
              <span className={`pill ${statusClass(r.status)}`}>{r.status}</span>
              <span>{r.skill || "—"}</span>
              <span>{fmtMs(r.wall_time_ms)}</span>
              <span className={styles.timestamp}>{fmtTime(r.started_at)}</span>
            </div>
          </div>
        );
      })}
    </>
  );
}
