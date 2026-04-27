import LearnShell from "../LearnShell";
import styles from "../learn.module.css";

export default function LearnArchitecture() {
  return (
    <LearnShell crumb="Architecture" active="arch">
      <h1>How this is built</h1>
      <p className={styles.subtitle}>
        The pipeline stages, the backend registry, where Postgres fits, and
        why the dashboard is a single static page.
      </p>

      <h2>Pipeline overview</h2>
      <p>
        Six stages, each in its own module under{" "}
        <code>orchestrator/pipeline/</code>:
      </p>
      <ol>
        <li>
          <strong>Decomposer</strong> — natural language to typed problem
          graph, via Gemma 4 31B (vLLM primary, Ollama fallback).
        </li>
        <li>
          <strong>Formulator</strong> — routes each problem to a
          skill-specific formulator that builds the backend-ready input.
        </li>
        <li>
          <strong>Dispatcher</strong> — reads <code>config/backends.yaml</code>
          , consults learned preferences (Phase 2), and picks the top-k
          backends to race. Assigns each GPU-bound backend a lane.
        </li>
        <li>
          <strong>Backends</strong> — execute in parallel. Each backend module
          exposes a <code>run(input, gpu_lane)</code> function returning a
          typed Solution. Blocking solvers run on threads via{" "}
          <code>asyncio.to_thread</code>.
        </li>
        <li>
          <strong>Evaluator</strong> — routes to a skill-specific evaluator
          that scores each Solution. <code>pick_winner()</code> sorts by
          quality desc, wall-time asc.
        </li>
        <li>
          <strong>Reassembler</strong> — walks the problem graph bottom-up,
          combining outcomes into the final answer.
        </li>
      </ol>

      <div className={styles.stub}>
        <strong>Coming next:</strong> a diagram of the pipeline with each
        stage&apos;s I/O types annotated, the dispatcher&apos;s GPU lane
        assignment animated, and the read-only replay-server pattern (FastAPI
        mounting the Next.js static export) that makes this a single static
        site.
      </div>
    </LearnShell>
  );
}
