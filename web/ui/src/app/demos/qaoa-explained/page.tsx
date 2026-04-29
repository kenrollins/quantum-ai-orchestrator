import Link from "next/link";
import {
  AiCallout,
  CodeBlock,
  DemoPage,
  DemoSection,
  StubNote,
} from "../DemoShell";

export default function Demo5() {
  return (
    <DemoPage
      cardNumber={5}
      totalCards={6}
      title="QAOA explained for ML engineers"
      hook="Parameterized quantum circuit + classical optimizer = same loop you already know. Watch the bitstring distribution sharpen as the optimizer trains."
    >
      <DemoSection title="What this is">
        <p>
          QAOA is the Quantum Approximate Optimization Algorithm. Despite
          the name, the structure is intentionally familiar to anyone who
          has trained an ML model:
        </p>
        <ol>
          <li>
            <strong>Parameterized model</strong> — a quantum circuit with
            tunable angles γ<sub>1</sub>...γ<sub>L</sub> and β<sub>1</sub>...β<sub>L</sub> alternating between &ldquo;cost
            kernels&rdquo; (apply the optimization Hamiltonian for time γ) and
            &ldquo;mixer kernels&rdquo; (apply a transverse-field mixer for time β).
            Two parameters per layer, L layers deep.
          </li>
          <li>
            <strong>Loss</strong> — the expectation value of the cost
            Hamiltonian on the circuit&apos;s output state. For a QUBO encoded
            in Ising form, this is just the mean energy of the bitstring
            distribution the circuit produces.
          </li>
          <li>
            <strong>Optimizer</strong> — a classical minimizer (we use
            COBYLA) that adjusts the γ and β parameters to lower the loss.
            Same gradient-descent-shaped loop, except the &ldquo;forward pass&rdquo; is
            running the parameterized circuit on a GPU simulator.
          </li>
          <li>
            <strong>Sampling</strong> — once the parameters converge, run the
            circuit one more time and sample bitstrings. The distribution is
            sharply peaked at the optimal solutions; pick the most-frequent
            (or the one with minimum cost among the top-K).
          </li>
        </ol>
        <p>
          QAOA isn&apos;t magic. The parameterization is fixed in advance,
          the optimization is done classically, and on small problems
          today&apos;s QAOA at moderate depth often loses to a classical
          exact solver. The interesting part is that the algorithm
          generalizes — at sufficient depth, QAOA approaches the optimal
          solution; in the limit it&apos;s equivalent to adiabatic quantum
          computing.
        </p>
      </DemoSection>

      <DemoSection title="The kernel construction (CUDA-Q)">
        <CodeBlock filepath="infra/cudaq-worker/qaoa_worker.py" language="python">
{`def _build_qaoa(num_qubits, num_layers, h, J):
    """Standard QAOA ansatz: alternating cost + mixer layers."""
    kernel, params = cudaq.make_kernel(list)
    qubits = kernel.qalloc(num_qubits)
    kernel.h(qubits)  # Initial uniform superposition

    for layer in range(num_layers):
        gamma_idx, beta_idx = layer, num_layers + layer

        # Cost layer: e^{-i gamma H_cost}
        for i in range(num_qubits):
            if h[i] != 0:
                kernel.rz(2.0 * float(h[i]) * params[gamma_idx], qubits[i])
        for i in range(num_qubits):
            for j in range(i + 1, num_qubits):
                if J[i, j] != 0:
                    kernel.cx(qubits[i], qubits[j])
                    kernel.rz(2.0 * float(J[i, j]) * params[gamma_idx], qubits[j])
                    kernel.cx(qubits[i], qubits[j])

        # Mixer layer: e^{-i beta H_mixer}, H_mixer = sum_i X_i
        for i in range(num_qubits):
            kernel.rx(2.0 * params[beta_idx], qubits[i])

    return kernel`}
        </CodeBlock>
        <p>
          That&apos;s it. Two parameters per layer, alternating cost-Hamiltonian
          and X-mixer rotations, on top of an initial Hadamard layer that
          puts the qubits in uniform superposition. Everything else
          (parameter optimization, sampling, target selection by problem
          size) is plumbing.
        </p>
      </DemoSection>

      <StubNote>
        <p>
          <strong>Coming next.</strong> The most ML-legible thing about QAOA
          is watching the bitstring distribution sharpen as the optimizer
          runs:
        </p>
        <ul>
          <li>
            A Recharts <code>BarChart</code> with one bar per sampled
            bitstring (x-axis), height = sample count (y-axis).
          </li>
          <li>
            A slider scrubbing through optimizer iterations 0..N.
          </li>
          <li>
            Iteration 0: nearly flat distribution (random guesses, the
            initial Hadamard state).
          </li>
          <li>
            Iteration 50: a few bars tower above the rest. <em>Those</em> are
            the candidate solutions the optimizer found.
          </li>
        </ul>
        <p>
          To capture the data, we&apos;ll modify the cudaq-worker to record
          per-iteration bitstring histograms during the optimization and
          stream them back as part of the Solution payload. Recording adds
          ~20% overhead because we have to sample at each iteration; reasonable
          for a demo, gated behind a flag for production.
        </p>
      </StubNote>

      <AiCallout>
        QAOA isn&apos;t AI per se — it&apos;s a fixed-form quantum algorithm
        with classically tuned parameters. But the framing &ldquo;parameterized
        model + classical optimizer = trainable system&rdquo; is exactly the
        ML pattern. Frameworks like CUDA-Q expose QAOA as one stop in a
        family that includes VQE (variational quantum eigensolver),
        quantum-classical hybrid neural nets, and parameterized ansätze for
        chemistry. The same{" "}
        <code>cudaq.optimizers.COBYLA</code> + <code>cudaq.vqe</code> harness
        we use here is what runs all of them. The orchestration thesis
        applied to optimization: classical exact for small, simulated
        annealing for medium, gate-model for the regimes where today&apos;s
        algorithms genuinely benefit.
      </AiCallout>

      <DemoSection title="Until the histogram lands">
        <p>
          See QAOA running in <Link href="/demos/qubo-encoding">Demo #4</Link>{" "}
          (the QUBO race) or{" "}
          <Link href="/demos/orchestration">Demo #6</Link> (the orchestrator
          dashboard). The cudaq-worker entry point is{" "}
          <code>infra/cudaq-worker/qaoa_worker.py</code> — under 250 lines,
          stdin/stdout JSON protocol, runs in NVIDIA&apos;s cuda-quantum
          container.
        </p>
      </DemoSection>
    </DemoPage>
  );
}
