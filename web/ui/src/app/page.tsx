"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchHealth } from "@/lib/api";
import RunList from "@/components/RunList";
import RunDetail from "@/components/RunDetail";
import styles from "./page.module.css";

export default function Page() {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [healthOk, setHealthOk] = useState<boolean | null>(null);
  const [healthLabel, setHealthLabel] = useState<string>("connecting...");

  const refreshHealth = useCallback(async () => {
    try {
      const h = await fetchHealth();
      setHealthOk(true);
      setHealthLabel(`connected · ${h.postgres.db}`);
    } catch {
      setHealthOk(false);
      setHealthLabel("API unreachable");
    }
  }, []);

  useEffect(() => {
    refreshHealth();
    const id = setInterval(refreshHealth, 10_000);
    return () => clearInterval(id);
  }, [refreshHealth]);

  const dotColor = healthOk ? "var(--good)" : healthOk === false ? "var(--bad)" : "var(--text-dim)";

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div className={styles.title}>quantum-ai-orchestrator</div>
        <div style={{ color: "var(--text-dim)", fontSize: 12 }}>
          <span
            style={{
              display: "inline-block",
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: dotColor,
              marginRight: 4,
              verticalAlign: 1,
            }}
          />
          {healthLabel}
        </div>
        <div className={styles.footnote}>
          Phase 1 dashboard · post-hoc replay · no QPU · GPUs only
        </div>
      </header>

      <aside className={styles.sidebar}>
        <RunList selectedRunId={selectedRunId} onSelect={setSelectedRunId} />
      </aside>

      <main className={styles.main}>
        <RunDetail runId={selectedRunId} />
      </main>
    </div>
  );
}
