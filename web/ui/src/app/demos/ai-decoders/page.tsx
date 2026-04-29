import {
  AiCallout,
  CodeBlock,
  DemoPage,
  DemoSection,
  MiniMetric,
} from "../DemoShell";
import PredecoderPipelineDiagram from "@/components/PredecoderPipelineDiagram";
import QecLerCurve from "@/components/QecLerCurve";
import SurfaceCodeWidget from "@/components/SurfaceCodeWidget";

export default function Demo1() {
  return (
    <DemoPage
      cardNumber={1}
      totalCards={6}
      title="AI predecoders for surface codes"
      hook="A 3D-CNN whispers high-confidence local corrections, a classical matching decoder cleans up the rest. Together they beat the classical decoder alone."
    >
      <DemoSection title="What this is">
        <p>
          A surface code is the dominant scheme for fault-tolerant quantum
          computing — many physical qubits arranged in a lattice, voting to
          protect one logical qubit. Every cycle (roughly every microsecond),
          the lattice produces a noisy syndrome: a vector of parity-check bits
          that hints at where errors happened. A <em>decoder</em> turns that
          syndrome into a correction.
        </p>
        <p>
          The classical baseline is{" "}
          <strong>Minimum-Weight Perfect Matching</strong> (MWPM), implemented
          in PyMatching. It models the syndrome as a graph and finds the
          lowest-weight edge cover that pairs lit syndromes. Fast,
          well-understood, and the comparator everyone publishes against.
        </p>
        <p>
          NVIDIA&apos;s Ising decoder family (released April 2026 on World
          Quantum Day) is a 3D-CNN <em>predecoder</em>. It runs first, on the
          GPU, and emits a <em>modified</em> syndrome — easy local errors
          already cleaned up. PyMatching then runs on the modified syndrome on
          the CPU. The two cooperate: AI handles dense local mistakes
          quickly, MWPM handles the long error chains it was built for.
        </p>
      </DemoSection>

      <DemoSection title="The cooperative pipeline">
        <PredecoderPipelineDiagram />
      </DemoSection>

      <DemoSection title="Try it yourself — what is a syndrome?">
        <p>
          Click data qubits to add errors; watch the adjacent stabilizer
          checks light up. Notice how a chain of three errors produces only
          two lit syndromes — at the chain&apos;s endpoints. The interior
          stabilizers each see an even number of errors, so their parity
          cancels. <em>That</em> is the property every decoder exploits.
        </p>
        <SurfaceCodeWidget distance={5} />
      </DemoSection>

      <DemoSection title="Live result: AI vs classical, across noise rates">
        <p>
          The chart below pulls real runs from this dashboard&apos;s history.
          Each point is a fresh syndrome batch decoded by all three backends
          on the same shots. Lower is better. The AI predecoder beats classical
          MWPM at every noise rate we&apos;ve sampled, with the gap widest
          around p=0.005 — the model&apos;s training-distribution sweet spot.
        </p>
        <QecLerCurve distance={5} />
        <p style={{ marginTop: 12 }}>
          <MiniMetric label="lattice" value="d=5 rotated surface code" />
          <MiniMetric label="rounds" value="T=5" />
          <MiniMetric label="basis" value="X" />
          <MiniMetric label="GPU" value="2× RTX 6000 Ada (one decoder per lane)" />
        </p>
      </DemoSection>

      <DemoSection title="How it works (the 30 lines that matter)">
        <p>
          Each decoder takes a tensor of detection events and returns a
          tensor of predicted observable flips. The Ising backend wraps a
          PyTorch <code>3D-CNN</code> forward pass plus a residual-syndrome
          construction; PyMatching is a one-liner once the detector error
          model (DEM) is built.
        </p>
        <CodeBlock filepath="orchestrator/quantum/backends/_ising_common.py" language="python">
{`# Forward pass on the GPU lane assigned by the dispatcher.
device = torch.device(f"cuda:{gpu_lane}")
model = _load_model(variant, distance, n_rounds, device)

with torch.no_grad():
    logits = model(trainX_t)  # (B, 4, T, D, D)
    residual, pre_L = _compute_residual_full(
        logits=logits,
        x_syn_diff=x_syn_diff_t,
        z_syn_diff=z_syn_diff_t,
        detection_events=detection_events_t,
        num_boundary_dets=num_boundary_dets,
        maps=maps,
        distance=D,
        basis=basis,
    )

# PyMatching MWPM as the global step (CPU, microseconds).
matching_predictions = _decode_residual_pymatching(residual.cpu().numpy(), dem_str)

# Final logical prediction: matching's output XOR the predecoder's
# logical-frame contribution from data corrections.
predictions = (matching_predictions ^ pre_L_np.reshape(-1, 1)).astype(np.uint8)`}
        </CodeBlock>
        <p>
          The <code>_compute_residual_full</code> step is the magic: it takes
          the predecoder&apos;s 4-channel output (predicted X errors on data,
          predicted Z errors on data, predicted X stabilizer errors, predicted
          Z stabilizer errors), turns it into a modified-syndrome tensor, and
          extracts a logical-frame contribution that the matching decoder
          doesn&apos;t see. The two pipelines reconstruct each other&apos;s
          assumptions and the answer drops out.
        </p>
      </DemoSection>

      <AiCallout>
        Surface-code decoding is a domain where AI integrates cleanly because
        the problem is <em>local with structured global constraints</em>. A 3D-CNN
        excels at the local pattern-matching (correlated errors in nearby
        spacetime cells); a classical algorithm excels at the global
        bookkeeping. Pairing them is faster and more accurate than either
        alone, and runs on commodity GPUs. NVIDIA released the Ising weights
        publicly as Apache-2.0 — the same code in this repo loads them
        directly.
      </AiCallout>

      <DemoSection title="Further reading">
        <ul>
          <li>
            <a href="https://nvidia.github.io/cuda-quantum/blogs/blog/2026/04/14/cudaq-qec-0.6/">
              NVIDIA — CUDA-Q QEC 0.6 with Ising
            </a>{" "}
            (cooperative-predecoder framing, regime maps)
          </li>
          <li>
            <a href="https://research.google/blog/making-quantum-error-correction-work/">
              Google Research — Making quantum error correction work
            </a>{" "}
            (the Willow result; lattice diagrams)
          </li>
          <li>
            <a href="https://github.com/oscarhiggott/PyMatching">PyMatching</a> and{" "}
            <a href="https://github.com/quantumlib/Stim">Stim</a> — the libraries this demo runs on
          </li>
        </ul>
      </DemoSection>
    </DemoPage>
  );
}
