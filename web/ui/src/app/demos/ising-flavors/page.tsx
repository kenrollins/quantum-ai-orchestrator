import Link from "next/link";
import {
  AiCallout,
  DemoPage,
  DemoSection,
  MiniMetric,
  StubNote,
} from "../DemoShell";

export default function Demo3() {
  return (
    <DemoPage
      cardNumber={3}
      totalCards={6}
      title="NVIDIA Ising in three flavors"
      hook="Same 3D-CNN architecture, different operating points: Fast (R=9, ~900k params) vs Accurate (R=13, ~1.8M params) vs FP8 quantized for deployment."
    >
      <DemoSection title="What this is">
        <p>
          NVIDIA&apos;s Ising decoder family ships as a small set of
          variants. They&apos;re all the same{" "}
          <code>PreDecoderModelMemory_v1</code> architecture (a stack of 3D
          convolutional blocks with GELU activations) — just different
          configurations of layer count, kernel size, and channel widths.
          Each variant is one operating point on the latency-vs-accuracy
          curve, parameterized by <em>receptive field</em> (R) — how far in
          spacetime each output cell&apos;s prediction depends on input
          cells.
        </p>
        <p>
          The two we ship in this dashboard:
        </p>
        <ul>
          <li>
            <strong>Fast</strong> — Model 1, R=9, 4 conv layers, kernel size
            3, ~912k parameters. Lower latency, lower LER reduction.{" "}
            <code>fast/ising_decoder_surface_code_1_fast_r9_v1.0.77_fp16.safetensors</code>
          </li>
          <li>
            <strong>Accurate</strong> — Model 4, R=13, 6 conv layers, kernel
            size 3, ~1.8M parameters. Higher latency, higher LER reduction.{" "}
            <code>accurate/ising_decoder_surface_code_1_accurate_r13_v1.0.86_fp16.safetensors</code>
          </li>
        </ul>
        <p>
          NVIDIA also ships an FP8-quantized export for deployment via
          TensorRT — same model, half the memory, sub-microsecond inference
          on Hopper-class GPUs. We don&apos;t run that pipeline here yet (no
          ONNX/TensorRT in the host venv) but the export format is
          documented in the Ising-Decoding repo and the path is small.
        </p>
      </DemoSection>

      <DemoSection title="Live state in this dashboard">
        <p>
          Both Fast and Accurate variants are loaded and racing today.
          Forward pass timings on the workstation&apos;s RTX 6000 Ada GPUs:
        </p>
        <p>
          <MiniMetric label="Fast forward" value="~17–130 ms (cold → warm)" />
          <MiniMetric label="Accurate forward" value="~30–60 ms warmed" />
          <MiniMetric label="Fast params" value="912 k" />
          <MiniMetric label="Accurate params" value="1.8 M" />
          <MiniMetric label="weights" value="bf16 .safetensors" />
        </p>
        <p>
          The bake-off in <Link href="/demos/ai-decoders">Demo #1</Link> shows
          both variants competing simultaneously on each QEC race —
          ising_speed lands GPU 0, ising_accuracy lands GPU 1, and PyMatching
          runs on the CPU as the baseline.
        </p>
      </DemoSection>

      <StubNote>
        <p>
          <strong>Coming next.</strong> Three additions to make the variants
          comparison concrete:
        </p>
        <ul>
          <li>
            A side-by-side card with each variant&apos;s LER and median
            forward-pass latency from the actual run history.
          </li>
          <li>
            A reproduction of NVIDIA&apos;s Figure 2 from the CUDA-Q QEC 0.6
            blog — a 2D &ldquo;operating regime&rdquo; map (latency on x, LER on y)
            with each variant placed at its measured operating point.
          </li>
          <li>
            FP8 quantization integration. Their Ising-Decoding repo includes
            an ONNX export pipeline; running it in the cuda-quantum container
            against our weights and timing the result is the smallest
            possible deployment-realism demo.
          </li>
        </ul>
      </StubNote>

      <AiCallout>
        Variant choice is itself an ML-engineering decision. Fast vs Accurate
        is the same trade-off as any production model serving question:
        bigger model, better predictions, longer latency. NVIDIA shipped both
        endpoints because realistic deployments care about both
        edge-of-syndrome-budget latency (Fast is what you race against the
        cycle) and best-quality offline analysis (Accurate is what you
        post-process logs with). The orchestrator is set up to dispatch to
        either based on context — today it races them; in Phase 2 the
        Strategist will pick based on problem shape and historical wins.
      </AiCallout>

      <DemoSection title="See for yourself">
        <p>
          The cooperative pipeline that uses both variants is in{" "}
          <Link href="/demos/ai-decoders">Demo #1</Link>. The actual model
          loader code lives at{" "}
          <code>orchestrator/quantum/backends/_ising_common.py</code> — both
          variants share the same loader; the variant identity (
          <code>IsingVariant</code>) just specifies model id and weights path.
        </p>
      </DemoSection>
    </DemoPage>
  );
}
