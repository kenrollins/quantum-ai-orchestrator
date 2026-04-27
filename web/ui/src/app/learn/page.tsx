import Link from "next/link";
import LearnShell from "./LearnShell";
import styles from "./learn.module.css";

export default function LearnIndex() {
  return (
    <LearnShell crumb="Overview" active="index">
      <h1>Learn</h1>
      <p className={styles.subtitle}>
        Background you might want before driving the dashboard.
      </p>

      <p>
        This site is the conceptual companion to the orchestrator dashboard.
        It exists because the dashboard assumes you know what a surface code
        is, what a QUBO is, and why anyone would race quantum and classical
        solvers against each other. If those words are familiar, you can skip
        ahead to a track. If they aren&apos;t, start with the QEC track —
        it&apos;s where the most-likely-unfamiliar concepts live.
      </p>

      <p>
        The audience this is written for: engineers who know LLMs, GPUs, and
        machine learning, but may not have spent time on quantum computing.
        We assume comfort with linear algebra, probability, and gradient-based
        optimization; we don&apos;t assume comfort with stabilizer formalism
        or noise-channel decompositions. Anywhere you&apos;d need either, we
        ground it in something a software engineer already knows.
      </p>

      <h2>Tracks</h2>

      <Link href="/learn/qec" className={styles.tocCard}>
        <h3>Quantum error correction →</h3>
        <p>
          Why physical qubits are too noisy to compute with directly. How a
          surface code encodes one logical qubit across many physical ones.
          What a syndrome is and what a decoder does. How NVIDIA&apos;s open
          AI predecoder cooperates with classical decoders rather than
          replacing them.
        </p>
      </Link>

      <Link href="/learn/orchestration" className={styles.tocCard}>
        <h3>The orchestration pattern →</h3>
        <p>
          Why race solvers? What a QUBO is and why it&apos;s the lingua franca
          for quantum-inspired hardware. How QAOA works, framed as
          &ldquo;parameterized circuit + classical optimizer&rdquo; — the
          ML-engineer mental model.
        </p>
      </Link>

      <Link href="/learn/architecture" className={styles.tocCard}>
        <h3>How this is built →</h3>
        <p>
          The pipeline stages, the backend registry, the dispatcher&apos;s
          GPU lane assignment, where Postgres fits, and the read-only
          replay-server pattern that makes the dashboard a single static
          page.
        </p>
      </Link>

      <h2>Where these ideas come from</h2>

      <p>
        Most of the surface-code framing follows the conventions in{" "}
        <a href="https://research.google/blog/making-quantum-error-correction-work/">Google&apos;s
        Willow blog post</a>. The cooperative-predecoder framing is{" "}
        <a href="https://nvidia.github.io/cuda-quantum/blogs/blog/2026/04/14/cudaq-qec-0.6/">NVIDIA&apos;s
        from their CUDA-Q QEC 0.6 release</a>. The interactive surface-code
        widgets are adapted from{" "}
        <a href="https://arthurpesah.me/blog/2023-05-13-surface-code/">Arthur
        Pesah&apos;s MIT-licensed explainer</a>. The QAOA framing follows the{" "}
        <a href="https://github.com/NVIDIA/cuda-q-academic/tree/main/qaoa-for-max-cut">CUDA-Q
        Academic Max-Cut tutorial</a>.
      </p>

      <p>
        Where this differs from those sources: every concept here is grounded
        in something the actual code in this repo is doing. The decoder
        diagrams describe the predecoder + PyMatching pipeline that ships in{" "}
        <code>orchestrator/quantum/backends/_ising_common.py</code>, not a
        generic teaching example. The QAOA explanation matches what{" "}
        <code>infra/cudaq-worker/qaoa_worker.py</code> runs in the
        cuda-quantum container.
      </p>
    </LearnShell>
  );
}
