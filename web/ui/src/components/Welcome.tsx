"use client";

import Link from "next/link";
import styles from "./Welcome.module.css";

/**
 * Empty-state landing copy. First thing a self-serve visitor sees.
 * The job is "you arrived here cold from GitHub — here is what this is and
 * what to click first." Three short paragraphs max.
 */
export default function Welcome() {
  return (
    <div className={styles.welcome}>
      <h1>quantum-ai-orchestrator</h1>
      <p className={styles.tagline}>
        AI-orchestrated control plane for hybrid quantum-classical workloads.
      </p>

      <p>
        Type a problem in plain English. An LLM (Gemma 4 31B) figures out what
        kind of problem it is and extracts the parameters. The orchestrator
        formulates the data each backend needs, then races three solvers in
        parallel — some classical, some quantum-inspired, some quantum
        simulation — across the workstation&apos;s GPUs. The winner is whoever
        scores highest. Every dispatch is recorded so the system can learn
        which backends fit which problems.
      </p>

      <p>
        Two demo asks ship today. Each shows up in the run list on the left;
        click either one to see its race.
      </p>

      <div className={styles.twoCol}>
        <div className={styles.demoCard}>
          <h3>Demo 1 · the federal hero</h3>
          <h4>Quantum error correction</h4>
          <p>
            <code>decode a distance-5 surface code at p=0.005</code>
            <br />
            NVIDIA&apos;s open-weights AI predecoder vs the classical PyMatching
            baseline, on simulated surface-code syndromes. The chart shows AI
            beating classical at every noise rate.
          </p>
        </div>
        <div className={styles.demoCard}>
          <h3>Demo 2 · the orchestration thesis</h3>
          <h4>Mission assignment</h4>
          <p>
            <code>assign 12 assets across 8 tasks with K=3</code>
            <br />
            Classical exact, quantum-inspired annealing, and CUDA-Q QAOA race a
            small QUBO. Today the classical solver wins. As problems grow, the
            quantum substrates start to be competitive.
          </p>
        </div>
      </div>

      <div className={styles.cta}>
        <span>New to quantum? </span>
        <Link href="/learn">
          <span className={styles.arrow}>→</span> Read the conceptual background
        </Link>
        <span style={{ marginLeft: "auto", fontSize: 11 }}>
          No QPU required · Phase 1 demo · runs on Dell Precision workstation GPUs
        </span>
      </div>
    </div>
  );
}
