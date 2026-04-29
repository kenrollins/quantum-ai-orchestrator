import Link from "next/link";
import { DemosShell } from "./DemoShell";
import styles from "./demos.module.css";

interface CardSpec {
  num: number;
  slug: string;
  title: string;
  lesson: string;
  status: "full" | "stub";
  tags: string[];
}

/**
 * The catalog. Each entry is one AI-quantum integration pattern.
 * Six cards ship with Phase 1.D; cards 1, 4, 6 have full content,
 * cards 2, 3, 5 are stubbed with what's coming.
 */
const CARDS: CardSpec[] = [
  {
    num: 1,
    slug: "ai-decoders",
    title: "AI predecoders for surface codes",
    lesson:
      "A 3D-CNN whispers high-confidence local corrections, a classical matching decoder cleans up the rest. Together they beat the classical decoder alone.",
    status: "full",
    tags: ["NVIDIA Ising", "PyMatching", "Stim", "GPU"],
  },
  {
    num: 2,
    slug: "decoder-scaling",
    title: "Decoder cost scales exponentially with code distance",
    lesson:
      "More physical qubits → fewer logical errors, but only if your decoder runs in the syndrome-cycle budget. AI predecoders extend that budget.",
    status: "stub",
    tags: ["surface code", "logical error rate", "latency"],
  },
  {
    num: 3,
    slug: "ising-flavors",
    title: "NVIDIA Ising in three flavors",
    lesson:
      "Same 3D-CNN architecture, different operating points: Fast (R=9, ~900k params) vs Accurate (R=13, ~1.8M params) vs FP8 quantized for deployment.",
    status: "stub",
    tags: ["NVIDIA Ising", "model variants", "FP8", "deployment"],
  },
  {
    num: 4,
    slug: "qubo-encoding",
    title: "From QUBO to quantum: encoding optimization",
    lesson:
      "The same assignment problem encoded as a Lagrangian-penalty QUBO, then solved by classical exact, simulated annealing, and gate-model QAOA. See where the substrates diverge.",
    status: "full",
    tags: ["QUBO", "OR-Tools", "D-Wave neal", "CUDA-Q QAOA"],
  },
  {
    num: 5,
    slug: "qaoa-explained",
    title: "QAOA explained for ML engineers",
    lesson:
      "Parameterized quantum circuit + classical optimizer = same loop you already know. Watch the bitstring distribution sharpen as the optimizer trains.",
    status: "stub",
    tags: ["CUDA-Q", "QAOA", "VQE", "optimizer"],
  },
  {
    num: 6,
    slug: "orchestration",
    title: "Why orchestration matters",
    lesson:
      "One natural-language ask, three substrates, a parallel race. Sometimes classical wins. Sometimes annealing wins. Sometimes quantum simulation refuses because the qubit count is too high. The 'winner' depends on the problem.",
    status: "full",
    tags: ["LLM decompose", "race", "Postgres provenance"],
  },
];

export default function DemosCatalog() {
  return (
    <DemosShell crumb="Catalog" active="catalog">
      <div className={styles.catalog}>
        <div className={styles.hero}>
          <h1>AI-quantum integration patterns</h1>
          <p className={styles.tagline}>
            A tour of how AI is showing up in quantum computing today, on
            real GPUs, with the code visible.
          </p>
          <p className={styles.lead}>
            Each card is one technique. We show what it does, how it&apos;s
            built, and where AI fits — with a small interactive demo or
            visualization driven by code that runs on the host workstation.
            No quantum-physics PhD assumed; familiarity with LLMs, GPUs, and
            ML is enough.
          </p>
        </div>

        <div className={styles.section}>The federal hero — NVIDIA Ising</div>
        <div className={styles.cardGrid}>
          {CARDS.filter((c) => [1, 2, 3].includes(c.num)).map((c) => (
            <DemoCard key={c.num} card={c} />
          ))}
        </div>

        <div className={styles.section}>Optimization on the orchestration thesis</div>
        <div className={styles.cardGrid}>
          {CARDS.filter((c) => [4, 5, 6].includes(c.num)).map((c) => (
            <DemoCard key={c.num} card={c} />
          ))}
        </div>

        <div className={styles.section}>What this dashboard is not</div>
        <div className={styles.demoSection}>
          <p style={{ fontSize: 13, color: "var(--text-dim)", lineHeight: 1.7 }}>
            Not a production orchestrator pretending to be one. Not a benchmark
            of NVIDIA Ising vs anything. Not a research artifact. It&apos;s a
            <em> teaching catalog</em>: each demo is a self-contained illustration
            of one AI-quantum integration pattern, designed for technical
            audiences who know AI but may not know quantum. The code that runs
            each demo is the same code that ships in this repo.
          </p>
          <p style={{ fontSize: 13, color: "var(--text-dim)", lineHeight: 1.7 }}>
            For deeper background, see the <Link href="/learn">Learn</Link>{" "}
            tracks. For the orchestrator product UI (the original Phase 1
            design), see <Link href="/orchestrator">Orchestrator</Link> — it&apos;s
            now a single demo (#6) rather than the whole product.
          </p>
        </div>
      </div>
    </DemosShell>
  );
}

function DemoCard({ card }: { card: CardSpec }) {
  return (
    <Link
      href={`/demos/${card.slug}`}
      className={`${styles.card}${card.status === "stub" ? " " + styles.stubbed : ""}`}
    >
      <div className={styles.cardHead}>
        <span className={styles.num}>Demo {card.num}</span>
        <span
          className={`${styles.statusPill} ${card.status === "full" ? styles.full : styles.stub}`}
        >
          {card.status === "full" ? "ready" : "stubbed"}
        </span>
      </div>
      <h3>{card.title}</h3>
      <p className={styles.lesson}>{card.lesson}</p>
      <div className={styles.meta}>
        {card.tags.map((t) => (
          <span key={t} className="pill">
            {t}
          </span>
        ))}
      </div>
    </Link>
  );
}
