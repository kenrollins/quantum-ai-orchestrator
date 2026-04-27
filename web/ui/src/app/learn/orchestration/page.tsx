import LearnShell from "../LearnShell";
import styles from "../learn.module.css";

export default function LearnOrchestration() {
  return (
    <LearnShell crumb="Orchestration track" active="orch">
      <h1>The orchestration pattern</h1>
      <p className={styles.subtitle}>
        Why race solvers? What a QUBO is. How QAOA works for someone who knows
        gradient descent.
      </p>

      <h2>Why race</h2>
      <p>
        In 2026, &ldquo;solving a hard optimization problem&rdquo; rarely
        means picking the one right algorithm. You have a problem; you have a
        portfolio of algorithms — some classical, some quantum-inspired, some
        gate-model quantum simulation. Which one wins depends on the
        problem&apos;s size, structure, sparsity, noise tolerance, and your
        hardware. The standard answer to &ldquo;I don&apos;t know in
        advance&rdquo; in computing is: race them, pick the winner, and
        record the result so you can learn over time.
      </p>
      <p>
        This is the orchestration thesis. The dashboard&apos;s mission_assignment
        runs are it in miniature: three solvers (CP-SAT, simulated annealing,
        QAOA) race the same QUBO. Today on the small problem instances we
        ship, the classical exact solver wins. As problems grow past
        CP-SAT&apos;s reach, the quantum-inspired and quantum-simulation
        backends become competitive — and the orchestrator&apos;s recorded
        history of wins and losses becomes the basis for predicting which
        backend to prefer for which problem shape (the <em>Strategist</em>,
        Phase 2).
      </p>

      <div className={styles.stub}>
        <strong>Coming next:</strong> what a QUBO is and why annealers and
        QAOA both consume it. The before/after Max-Cut visual from the
        CUDA-Q Academic tutorial, restyled. A QAOA bitstring-histogram
        animation that shows the optimizer pushing probability mass onto the
        good answers — &ldquo;oh, it&apos;s gradient descent&rdquo; for ML
        engineers.
      </div>
    </LearnShell>
  );
}
