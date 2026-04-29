import Link from "next/link";
import {
  AiCallout,
  CodeBlock,
  DemoPage,
  DemoSection,
  MiniMetric,
} from "../DemoShell";

export default function Demo6() {
  return (
    <DemoPage
      cardNumber={6}
      totalCards={6}
      title="Why orchestration matters"
      hook="One natural-language ask, three substrates, a parallel race. Sometimes classical wins. Sometimes annealing wins. Sometimes quantum simulation refuses because the qubit count is too high."
    >
      <DemoSection title="What this is">
        <p>
          The other five demos teach individual AI-quantum integration
          patterns. This one is the meta-pattern: a system that takes a
          natural-language ask, decomposes it via an LLM into a typed problem,
          dispatches across multiple substrates in parallel, scores them
          against a skill-specific metric, picks a winner, and records every
          decision for later analysis. Same input, multiple substrates,
          observable trade-offs.
        </p>
        <p>
          Why orchestration? Because in 2026 &ldquo;solving a hard problem with
          a quantum-relevant algorithm&rdquo; rarely means picking the one
          right algorithm. You have a problem, you have a portfolio of
          solvers (some classical, some quantum-inspired, some gate-model
          quantum simulation), and you don&apos;t know in advance which
          one wins on a specific instance. Race them, pick the winner, record
          the result, and over time you can predict the right substrate before
          dispatching.
        </p>
      </DemoSection>

      <DemoSection title="Try it">
        <p>
          The orchestrator UI lives at{" "}
          <Link href="/orchestrator">/orchestrator</Link>. Click any run in
          the left rail to see the bake-off. Two demo asks are pre-populated
          and reproducible from the CLI:
        </p>
        <CodeBlock language="bash">
{`# Quantum error correction (federal hero — see also Demo #1)
qao run "decode a distance-5 surface code at p=0.005 X basis 3000 shots"
# -> ising_accuracy wins with logical error rate 0.011
# -> 38% reduction vs the classical PyMatching baseline

# Mission assignment — the orchestration thesis in miniature
qao run "assign 12 assets across 8 tasks with capacity constraint K=3"
# -> classical_ortools wins with optimal cost 86
# -> neal feasible at 150
# -> cudaq_qaoa graceful refuse: 96 qubits exceeds 64-qubit GPU cap`}
        </CodeBlock>
      </DemoSection>

      <DemoSection title="The pipeline, six stages">
        <p>
          A natural-language ask flows through six modules, each in its own
          file under <code>orchestrator/pipeline/</code>:
        </p>
        <ol>
          <li>
            <strong>Decomposer</strong> — Gemma 4 31B running on vLLM emits a
            typed problem graph. Per ADR-0010 the default endpoint is the
            xr7620 gemma-forge box; local Ollama is the fallback.
          </li>
          <li>
            <strong>Formulator</strong> — routes each problem to a
            skill-specific formulator that builds the backend-ready input
            (Stim circuit + DEM for QEC; QUBO matrix for assignment).
          </li>
          <li>
            <strong>Dispatcher</strong> — reads the backend registry, picks
            top-K applicable backends, assigns each GPU-bound backend a lane
            (GPU 0 or GPU 1).
          </li>
          <li>
            <strong>Backends</strong> — execute in parallel via{" "}
            <code>asyncio.gather</code> over <code>asyncio.to_thread</code>{" "}
            (so blocking solvers don&apos;t stall the event loop).
          </li>
          <li>
            <strong>Evaluator</strong> — routes each Solution to the
            skill-specific evaluator. <code>pick_winner()</code> sorts by quality
            desc, wall-time asc.
          </li>
          <li>
            <strong>Reassembler</strong> — walks the problem graph bottom-up
            and produces the final answer.
          </li>
        </ol>
        <p>
          Every dispatch + outcome lands in Postgres
          (<code>common.dispatches</code> + <code>common.outcomes</code>),
          including losers. The dashboard reads that directly to render the
          bake-off.
        </p>
      </DemoSection>

      <DemoSection title="The decomposer call (where the LLM lives)">
        <CodeBlock filepath="orchestrator/pipeline/decomposer.py" language="python">
{`async def decompose(ask: str, run_id=None) -> ProblemGraph:
    """Convert natural language ask to a problem graph.

    Tries vLLM (default per ADR-0010); on connection error or 5xx,
    falls back to local Ollama with the same prompt. The forgiving
    parser absorbs Gemma's shape drift either way.
    """
    content: str | None = None
    runtime_used: str | None = None

    # Primary: vLLM at the gemma-forge endpoint.
    try:
        content = await _call_vllm(ask)
        runtime_used = f"vllm@{DECOMPOSER_BASE_URL}"
    except (APIConnectionError, APIStatusError, httpx.HTTPError, ValueError) as e:
        logger.warning("Decomposer primary (vLLM) failed: %s. Falling back.", e)

    # Fallback: local Ollama daemon.
    if content is None:
        content = await _call_ollama(ask)
        runtime_used = f"ollama@{DECOMPOSER_FALLBACK_URL}"

    data = _parse_response(content)
    return _to_problem_graph(run_id, ask, data)`}
        </CodeBlock>
        <p>
          Same model (Gemma 4 31B-it), two runtimes. vLLM-on-xr7620 is 2.3×
          faster wall-time and emits canonical JSON without shape drift; local
          Ollama is the resilience plan. The forgiving parser handles both.
        </p>
      </DemoSection>

      <DemoSection title="Live state">
        <p>
          <MiniMetric label="backends registered" value="6 (Phase 1)" />
          <MiniMetric label="skills" value="qec_decode, mission_assignment" />
          <MiniMetric label="GPU lanes" value="2 (RTX 6000 Ada × 2)" />
          <MiniMetric label="provenance" value="Postgres common.*" />
          <MiniMetric label="LLM" value="Gemma 4 31B-it" />
        </p>
      </DemoSection>

      <AiCallout>
        Three different AI-quantum integration points, all in the same pipeline.{" "}
        <strong>Decomposer</strong>: an LLM converts natural language into a
        typed problem graph — the exact translation a human would otherwise
        do by hand. <strong>Predecoder</strong>: a 3D-CNN on the GPU racing
        the classical decoder per Demo #1. <strong>Strategist (Phase 2)</strong>:
        analyzes the run history and learns which substrate to prefer for
        which problem shape. The orchestrator&apos;s value is composing them:
        the LLM at the front, the GPU-accelerated solvers in the middle, the
        learned dispatcher at the back.
      </AiCallout>

      <DemoSection title="See it run">
        <p>
          Open <Link href="/orchestrator">/orchestrator</Link>. Pick a recent
          run from the sidebar. The bake-off, the LER curve, the bipartite
          assignment overlay, the Stim circuit — all populated by the same
          pipeline you see here. The orchestrator is one demo among many in
          this catalog, not the whole product.
        </p>
      </DemoSection>
    </DemoPage>
  );
}
