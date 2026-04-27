"use client";

import type { DispatchRow, ProblemRow } from "@/lib/types";
import styles from "./AboutRun.module.css";

interface Props {
  problem: ProblemRow;
  dispatches: DispatchRow[];
}

/**
 * Skill-aware "what just happened" callout. Two short sentences max.
 * Pattern from the explainer-research bank: lead with the visual rule, then
 * the mechanism, then what to look for. No equations, no hedging, no implementation
 * leakage ("common.dispatches"). The audience is technical engineers who know
 * AI but may not know quantum.
 */
export default function AboutRun({ problem, dispatches }: Props) {
  if (problem.problem_class === "qec_syndrome") {
    return <QecAbout problem={problem} dispatches={dispatches} />;
  }
  if (problem.problem_class === "qubo_assignment") {
    return <AssignmentAbout problem={problem} dispatches={dispatches} />;
  }
  return null;
}

function QecAbout({ problem, dispatches }: Props) {
  const params = problem.params as Record<string, unknown>;
  const distance = num(params.distance);
  const noise = num(params.noise_rate);
  const shots = num(params.shots);

  const winner = dispatches.find((d) => d.is_winner);
  const baseline = dispatches.find((d) => d.backend_name === "pymatching");
  const winnerLer = winner ? lerOf(winner) : null;
  const baselineLer = baseline ? lerOf(baseline) : null;
  const reduction =
    winnerLer != null && baselineLer != null && baselineLer > 0
      ? ((baselineLer - winnerLer) / baselineLer) * 100
      : null;

  return (
    <div className={styles.about}>
      <div className={styles.label}>What just happened</div>
      <p>
        We simulated <strong className={styles.num}>{shots ?? "—"}</strong> noisy
        runs of a distance-<strong className={styles.num}>{distance ?? "—"}</strong>{" "}
        surface code at physical error rate{" "}
        <strong className={styles.num}>p={fmtP(noise)}</strong>. The surface code
        is a quantum-error-correction lattice — many physical qubits voting to
        protect one logical qubit. Each shot produces a noisy syndrome; the
        decoder&apos;s job is to guess where the errors actually were.
      </p>
      <p>
        Three decoders raced the same syndromes:{" "}
        <strong>PyMatching</strong> (the classical baseline, min-weight matching
        on the syndrome graph) and two variants of NVIDIA&apos;s{" "}
        <strong>Ising predecoder</strong> (a 3D-CNN that pre-corrects easy
        errors before PyMatching runs). The two cooperate — the AI handles
        local mistakes fast; PyMatching cleans up the rest.
        {winner && winnerLer != null && (
          <>
            {" "}
            <strong>{winner.backend_name}</strong> won with logical error
            rate <strong className={styles.num}>{winnerLer.toFixed(4)}</strong>
            {reduction != null && reduction > 1 && (
              <>
                {" "}— a <strong className={styles.num}>{reduction.toFixed(0)}%</strong>{" "}
                reduction vs the classical baseline alone
              </>
            )}
            .
          </>
        )}
      </p>
    </div>
  );
}

function AssignmentAbout({ problem, dispatches }: Props) {
  const params = problem.params as Record<string, unknown>;
  const assets = num(params.assets);
  const tasks = num(params.tasks);
  const capacity = num(params.capacity);

  const winner = dispatches.find((d) => d.is_winner);
  const winnerObj = winner
    ? num((winner.metric_payload as Record<string, unknown> | null)?.objective)
    : null;
  const feasible =
    (winner?.metric_payload as Record<string, unknown> | null)?.is_feasible;

  return (
    <div className={styles.about}>
      <div className={styles.label}>What just happened</div>
      <p>
        We solved a{" "}
        <strong className={styles.num}>
          {assets ?? "—"} asset × {tasks ?? "—"} task
        </strong>{" "}
        assignment problem with capacity{" "}
        <strong className={styles.num}>K={capacity ?? "—"}</strong>. Each asset
        can take up to K tasks. Each (asset, task) pair has a cost. The goal is
        to assign every task to exactly one asset, minimizing total cost — a
        classical combinatorial optimization. We encode it as a QUBO (quadratic
        unconstrained binary optimization), the lingua franca for quantum
        annealers and gate-model algorithms.
      </p>
      <p>
        Three solvers raced the same QUBO:{" "}
        <strong>OR-Tools CP-SAT</strong> (Google&apos;s classical exact solver),{" "}
        <strong>D-Wave neal</strong> (simulated annealing — the quantum-inspired
        baseline), and <strong>CUDA-Q QAOA</strong> (NVIDIA&apos;s
        gate-model quantum algorithm running on a GPU).{" "}
        {winner && (
          <>
            <strong>{winner.backend_name}</strong> won
            {winnerObj != null && (
              <>
                {" "}
                with cost <strong className={styles.num}>{winnerObj}</strong>
                {feasible === true ? " (feasible)" : feasible === false ? " (constraints violated)" : ""}
              </>
            )}
            . On problems this small, exact classical solvers are hard to beat;
            on larger instances, the quantum-inspired and quantum-simulation
            backends start to be competitive — that&apos;s the orchestration
            thesis.
          </>
        )}
      </p>
    </div>
  );
}

function num(v: unknown): number | undefined {
  return typeof v === "number" ? v : undefined;
}

function lerOf(d: DispatchRow): number | null {
  const m = d.metric_payload as Record<string, unknown> | null;
  if (m && typeof m.ler === "number") return m.ler;
  return null;
}

function fmtP(p: number | undefined): string {
  if (p === undefined) return "—";
  if (p < 0.001) return p.toExponential(1);
  return p.toString();
}
