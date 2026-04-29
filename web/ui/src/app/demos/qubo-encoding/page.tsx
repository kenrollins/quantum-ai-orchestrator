import {
  AiCallout,
  CodeBlock,
  DemoPage,
  DemoSection,
  MiniMetric,
} from "../DemoShell";
import QuboHeatmap from "@/components/QuboHeatmap";

export default function Demo4() {
  return (
    <DemoPage
      cardNumber={4}
      totalCards={6}
      title="From QUBO to quantum: encoding optimization"
      hook="The same assignment problem encoded as a Lagrangian-penalty QUBO, then solved by classical-exact, simulated annealing, and gate-model QAOA. See where the substrates diverge."
    >
      <DemoSection title="What this is">
        <p>
          A surprising number of useful problems — vehicle routing,
          asset-task assignment, portfolio optimization, hyperparameter
          tuning — can be encoded as <strong>QUBO</strong>: Quadratic
          Unconstrained Binary Optimization. Variables are 0/1; the objective
          is a quadratic form <code>x<sup>T</sup>Qx</code>. Find the bitstring
          that minimizes that quantity.
        </p>
        <p>
          QUBO is the lingua franca of quantum-inspired hardware. D-Wave
          annealers consume it directly. Gate-model algorithms like QAOA
          consume it after a small transformation to Ising form
          (substitute <code>x = (1−s)/2</code> for spin-1/2 variables). And
          classical solvers like OR-Tools CP-SAT can solve QUBO-encoded
          assignment problems exactly via branch-and-bound. <em>Same
          problem, three substrates.</em>
        </p>
      </DemoSection>

      <DemoSection title="The encoding, step by step">
        <p>
          Take a small assignment: 5 assets, 4 tasks, capacity-2 (each asset
          can take at most 2 tasks). 20 binary variables: <code>x[i,j]=1</code> if
          asset i is assigned to task j. Two constraints: each task assigned
          exactly once, each asset gets ≤ 2 tasks.
        </p>
        <p>
          Constraints become quadratic penalty terms. <em>Each task
          assigned exactly once</em> is{" "}
          <code>(∑<sub>i</sub> x[i,j] − 1)<sup>2</sup></code> per task; expand
          and you get a <em>negative</em> linear term per variable plus a{" "}
          <em>positive</em> pairwise term per (i, i&apos;) pair within the same
          task. Multiply by a Lagrange multiplier
          large enough to dominate any cost saving. The standard rule of
          thumb is{" "}
          <code>penalty ≥ 2 × max(cost_matrix)</code>.
        </p>
        <CodeBlock filepath="skills/mission_assignment/formulator.py" language="python">
{`# Build the QUBO matrix (upper-triangular, 0/1 variables).
Q = np.zeros((num_vars, num_vars))

# (1) Cost terms on the diagonal.
for i in range(num_assets):
    for j in range(num_tasks):
        k = i * num_tasks + j
        Q[k, k] += cost_matrix[i, j]

# (2) Penalty: each task assigned exactly once.
# Expanding (sum_i x[i,j] - 1)^2 gives:
#   diagonal contribution -1 per (i, j) variable
#   off-diagonal contribution +2 per (i1, i2) pair on same task
for j in range(num_tasks):
    for i in range(num_assets):
        Q[i * num_tasks + j, i * num_tasks + j] -= penalty_scale
    for i1 in range(num_assets):
        for i2 in range(i1 + 1, num_assets):
            Q[i1 * num_tasks + j, i2 * num_tasks + j] += 2 * penalty_scale

# (3) Capacity penalty: pairs within the same asset get a soft penalty.
for i in range(num_assets):
    for j1 in range(num_tasks):
        for j2 in range(j1 + 1, num_tasks):
            Q[i * num_tasks + j1, i * num_tasks + j2] += penalty_scale * 0.5 / capacity`}
        </CodeBlock>
        <p>
          For our 5×4 K=2 example that produces a 20×20 matrix. The structure
          is hand-recognizable: dense blocks on the diagonal (cost + per-task
          penalty), off-diagonal stripes (per-asset capacity penalty). Hover
          a cell to see its origin.
        </p>
      </DemoSection>

      <DemoSection title="See the matrix">
        <QuboHeatmap />
      </DemoSection>

      <DemoSection title="Three solvers consume the same Q">
        <p>
          Once Q exists, the orchestrator hands it to whichever backends
          apply. For QUBO assignment, that&apos;s three:
        </p>
        <ul>
          <li>
            <strong>OR-Tools CP-SAT</strong> — Google&apos;s exact constraint
            solver. Treats the assignment natively (it doesn&apos;t need the
            Lagrangian penalties; it has hard constraints). Wins on small
            instances. Can&apos;t scale past a few hundred variables.
          </li>
          <li>
            <strong>D-Wave neal</strong> — simulated annealing. Reads the
            QUBO directly, runs Metropolis-style flips at decreasing
            temperature, returns the lowest-energy sample seen. Quantum-inspired
            (the algorithm mimics what a quantum annealer would do).
          </li>
          <li>
            <strong>CUDA-Q QAOA</strong> — gate-model quantum simulation.
            Converts the QUBO to Ising form, builds a parameterized circuit,
            runs VQE-style optimization, samples bitstrings. Today on small
            problems the classical exact solver tends to win; on larger
            instances QAOA can be competitive. See{" "}
            <a href="/demos/qaoa-explained">demo #5</a> for what QAOA is doing
            internally.
          </li>
        </ul>
        <p>
          <MiniMetric label="encoding" value="20-bit QUBO" />
          <MiniMetric label="solvers" value="3 in parallel" />
          <MiniMetric label="winner today" value="classical_ortools" />
          <MiniMetric label="orchestrator picks" value="based on size + history" />
        </p>
      </DemoSection>

      <AiCallout>
        AI doesn&apos;t directly solve the QUBO here; it sits at two
        different points in the pipeline. <strong>Upstream</strong>: a Gemma
        4 31B LLM reads the natural-language ask (&ldquo;assign 12 assets
        across 8 tasks K=3&rdquo;), recognizes it as a QUBO assignment, and
        emits the typed parameters this code consumes. <strong>Downstream</strong>:
        the Strategist (Phase 2) will read the history of which solver wins
        which problem shape and bias future dispatches. The QUBO formulation
        itself is classical math; the AI is the wrapper that decides what to
        encode and what to do with the result.
      </AiCallout>

      <DemoSection title="Further reading">
        <ul>
          <li>
            <a href="https://docs.ocean.dwavesys.com/en/stable/concepts/qubo.html">
              D-Wave Ocean docs — QUBO problems
            </a>
          </li>
          <li>
            <a href="https://nvidia.github.io/cuda-quantum/0.8.0/examples/python/tutorials/qaoa.html">
              CUDA-Q — Max-Cut with QAOA
            </a>{" "}
            (the canonical QAOA explainer)
          </li>
          <li>
            <a href="https://developers.google.com/optimization/cp/cp_solver">
              Google OR-Tools CP-SAT
            </a>{" "}
            — what classical exact looks like
          </li>
        </ul>
      </DemoSection>
    </DemoPage>
  );
}
