import LearnShell from "../LearnShell";
import PredecoderPipelineDiagram from "@/components/PredecoderPipelineDiagram";
import SurfaceCodeWidget from "@/components/SurfaceCodeWidget";
import styles from "../learn.module.css";

export default function LearnQec() {
  return (
    <LearnShell crumb="QEC track" active="qec">
      <h1>Quantum error correction</h1>
      <p className={styles.subtitle}>
        Why physical qubits are too noisy to use directly, and how a lattice
        of them voting protects one good logical qubit.
      </p>

      <h2>The problem</h2>
      <p>
        A classical bit, once written, holds its value reliably for years. A
        quantum bit (qubit) is the opposite: it decoheres in microseconds, and
        every operation you apply to it injects more error. Today&apos;s best
        physical qubits — the ones in IBM, Google, IonQ, Quantinuum, and
        Rigetti hardware — have per-gate error rates around{" "}
        <code>10⁻³</code> to <code>10⁻⁴</code>. To run an algorithm with a
        million gates, you need an effective error rate around{" "}
        <code>10⁻¹⁰</code> or better. There is no realistic path to that from
        physics alone. The physics improves slowly. The arithmetic doesn&apos;t.
      </p>
      <p>
        The way out is the same as in classical communication: encode redundantly.
        Spread one logical bit&apos;s information across many physical bits in a
        way that lets a decoder catch and correct errors before they compound.
        The dominant scheme in fault-tolerant quantum computing is the{" "}
        <strong>surface code</strong>.
      </p>

      <div className={styles.pause}>
        <strong>Quick analogy.</strong> A surface code is to a qubit what a
        Reed-Solomon code is to a hard drive sector — except the encoding
        runs continuously while the data is in flight, not just at write time,
        because the qubit is decohering the entire time you&apos;re using it.
      </div>

      <h2>The surface code, in three sentences</h2>
      <p>
        A surface code arranges physical qubits in a square lattice. Some
        positions are <em>data qubits</em> (carrying the information); the
        rest are <em>measurement qubits</em> (continuously polled to detect
        errors). A distance-d code uses roughly d² data qubits and can
        correct any combination of up to (d−1)/2 errors per round.
      </p>
      <p>
        The bigger the lattice, the more errors it can survive. Critically,
        if your physical error rate is below a certain threshold (around
        p ≈ 0.005 for the rotated surface code under realistic noise), then
        increasing d{" "}
        <em>exponentially</em> suppresses logical errors. You burn more
        physical qubits and get a much better logical qubit.
        <a href="https://research.google/blog/making-quantum-error-correction-work/">{" "}Google&apos;s
        Willow demonstration</a> in 2024 was the first hardware experiment to
        cross that threshold convincingly.
      </p>

      <SurfaceCodeWidget distance={5} />

      <h2>Decoders</h2>
      <p>
        Error correction has two halves. First, the lattice produces a stream
        of syndrome measurements every few microseconds — these are the dim
        flickers that signal &ldquo;something bad probably happened in this
        region.&rdquo; Second, a <strong>decoder</strong> reads those
        syndromes and figures out what the actual error was, so the system
        can apply a correction.
      </p>
      <p>
        The standard classical decoder is{" "}
        <strong>Minimum-Weight Perfect Matching</strong> (MWPM), implemented
        in libraries like{" "}
        <a href="https://github.com/oscarhiggott/PyMatching">PyMatching</a>.
        MWPM treats the syndrome as a graph: lit syndrome positions are
        vertices, and the decoder finds the lowest-weight set of edges that
        pairs them up. Each edge corresponds to a candidate error chain. It&apos;s
        fast, well-understood, and is the comparator everyone publishes
        against.
      </p>
      <p>
        MWPM is good. It is not optimal. The matching graph treats X and Z
        errors independently, ignores correlations between them, and uses
        edge weights derived from a noise model that&apos;s an approximation
        of the real device. That gap — the gap between MWPM&apos;s correction
        and the maximum-likelihood correction — is where AI decoders live.
      </p>

      <h2>The AI predecoder, and why it cooperates</h2>
      <p>
        In April 2026 NVIDIA released the <strong>Ising decoder</strong>{" "}
        family — open-weights 3D-CNNs trained on simulated surface-code
        syndromes.{" "}
        <a href="https://nvidia.github.io/cuda-quantum/blogs/blog/2026/04/14/cudaq-qec-0.6/">Their
        framing is the important part</a>: Ising is a <em>predecoder</em>,
        not a replacement for MWPM. It runs first, on the GPU, and outputs a
        <em>modified syndrome</em> — a syndrome with high-confidence local
        corrections already applied. PyMatching then runs on the modified
        syndrome on the CPU. The two cooperate.
      </p>

      <div className={styles.figure}>
        <PredecoderPipelineDiagram />
        <div className={styles.caption}>
          The cooperative pipeline. The AI predecoder pre-corrects easy local
          errors quickly on the GPU; PyMatching cleans up the rest on the
          CPU. The bottom path (skip the AI, run PyMatching alone) is the
          baseline against which we measure improvement.
        </div>
      </div>

      <p>
        Why this division of labor? Two reasons. First, a 3D-CNN on a GPU is
        much better than MWPM at &ldquo;is this region just one or two clear
        local errors I can clean up immediately?&rdquo; — these are the easy
        cases, and there are a lot of them. Second, MWPM is much better than
        a CNN at the <em>global</em> matching problem — the long error chains
        that span the whole lattice. Splitting the work plays to each side&apos;s
        strength.
      </p>
      <p>
        The published numbers on this cooperation are striking: 2.5× faster
        decoding and roughly 3× lower logical error rate than PyMatching alone,
        across the regime where the model was trained (p ≈ 0.003 to 0.006).
        Our own race in this dashboard reproduces about 1.4× LER reduction at
        the same p — the gap to NVIDIA&apos;s headline numbers is mostly
        thresholding and noise-model details, documented in the journal entry
        for this phase.
      </p>

      <div className={styles.pause}>
        <strong>What to look at.</strong> Open the dashboard, click any{" "}
        <code>qec_decode</code> run, and you&apos;ll see two skill panels: the{" "}
        <em>QEC Lab — LER vs noise rate</em> chart shows the cooperative
        pipeline beating the baseline at every noise rate; the <em>QEC Lab —
        Stim circuit</em> panel shows the actual rotated surface-code memory
        circuit being decoded. Same circuit goes to all three decoders, so
        the race is on identical syndromes.
      </div>

      <h2>What about a real quantum computer?</h2>
      <p>
        Everything in this demo runs on simulated syndromes. Stim
        (Craig Gidney&apos;s simulator) generates the noisy measurement
        outcomes; PyMatching and the Ising decoders process them; we score by
        comparing decoded predictions to the ground-truth observable flips
        Stim also provides. No QPU is in the loop.
      </p>
      <p>
        That&apos;s deliberate. The orchestrator is designed so that the
        moment a real QPU emits real syndromes, the existing pipeline runs
        unchanged: the formulator stays the same, the decoders stay the same,
        the dashboard stays the same. The simulator slot is just replaced.
        Today&apos;s GPU substrate is genuine — the Ising decoder really does
        run on the workstation&apos;s RTX 6000 Ada GPUs — but the syndrome
        source is simulated. We say so explicitly in the dashboard footer.
      </p>

      <h2>Further reading</h2>
      <ul>
        <li>
          <a href="https://research.google/blog/making-quantum-error-correction-work/">
            Google Research — Making quantum error correction work (2024)
          </a>{" "}
          — the Willow result, with the canonical lattice diagrams.
        </li>
        <li>
          <a href="https://nvidia.github.io/cuda-quantum/blogs/blog/2026/04/14/cudaq-qec-0.6/">
            NVIDIA — CUDA-Q QEC 0.6 with Ising
          </a>{" "}
          — the cooperative-predecoder framing, with regime maps.
        </li>
        <li>
          <a href="https://arthurpesah.me/blog/2023-05-13-surface-code/">
            Arthur Pesah — An interactive introduction to the surface code
          </a>{" "}
          — the source for the click-to-set-error widget pattern.
        </li>
        <li>
          <a href="https://github.com/oscarhiggott/PyMatching">PyMatching</a>{" "}
          and <a href="https://github.com/quantumlib/Stim">Stim</a> — the libraries this demo actually runs on top of.
        </li>
      </ul>
    </LearnShell>
  );
}
