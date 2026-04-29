import Link from "next/link";
import {
  AiCallout,
  DemoPage,
  DemoSection,
  StubNote,
} from "../DemoShell";

export default function Demo2() {
  return (
    <DemoPage
      cardNumber={2}
      totalCards={6}
      title="Decoder cost scales exponentially with code distance"
      hook="More physical qubits → fewer logical errors, but only if your decoder runs in the syndrome-cycle budget. AI predecoders extend that budget."
    >
      <DemoSection title="What this is">
        <p>
          A surface code at distance d uses roughly d² physical data qubits
          to protect one logical qubit. If the physical error rate p is below
          a threshold (≈0.005 for the rotated surface code under realistic
          noise), then increasing d <em>exponentially suppresses</em> logical
          errors. Doubling d cuts logical error rate by orders of magnitude —
          this is the scaling property that makes fault-tolerant quantum
          computing possible at all.
        </p>
        <p>
          The catch is timing. The lattice produces a syndrome every cycle
          (~1 µs on Google&apos;s Willow, comparable on other platforms). If
          your decoder takes longer than one cycle to process the previous
          syndrome, errors accumulate faster than you can correct them and
          the logical qubit dies. The decoder budget is the cycle time. AI
          predecoders <em>extend</em> that budget by handling the easy local
          cases on a GPU at sub-microsecond latency, leaving the hard global
          matching for a dedicated CPU-side decoder.
        </p>
      </DemoSection>

      <StubNote>
        <p>
          <strong>Coming next.</strong> A two-panel chart:
        </p>
        <ul>
          <li>
            <strong>Left:</strong> LER vs d at fixed p, on a log y-axis.
            Equally-spaced bands at d=3, 5, 7 demonstrate the exponential
            suppression visually (as in{" "}
            <a href="https://research.google/blog/making-quantum-error-correction-work/">
              Google&apos;s Willow plot
            </a>
            ). One line per decoder so you can see where AI vs classical
            diverge.
          </li>
          <li>
            <strong>Right:</strong> decoder latency per shot vs d, again per
            decoder. Adds a horizontal &ldquo;1 µs cycle budget&rdquo; line to make
            the timing constraint visible.
          </li>
        </ul>
        <p>
          The data is mostly there in <code>common.outcomes</code> already (we
          record <code>wall_time_ms</code> per dispatch). The missing piece is
          systematic runs across multiple distances; today the dashboard
          history is heavy on d=5 because that&apos;s our acceptance ask.
          Adding a small &ldquo;sweep&rdquo; CLI command would fill it in.
        </p>
      </StubNote>

      <AiCallout>
        Scaling decoders is where AI integration matters most pragmatically.
        Classical MWPM gets <em>slower</em> as d grows (graph size scales
        with d²·T, matching is polynomial). A 3D-CNN&apos;s per-shot cost
        is bounded by its receptive field, which is fixed — it doesn&apos;t
        grow with d. So at large d the AI half of the cooperative pipeline
        becomes proportionally more important. NVIDIA&apos;s Ising paper
        reports decoders that fit in the cycle budget at d up to 13.
      </AiCallout>

      <DemoSection title="Until then">
        <p>
          See <Link href="/demos/ai-decoders">Demo #1</Link> for the
          AI-vs-classical comparison at fixed d=5, and the{" "}
          <Link href="/learn/qec">QEC track in /learn</Link> for the
          conceptual background on threshold scaling.
        </p>
      </DemoSection>
    </DemoPage>
  );
}
