---
id: journey-01-phase0-complete
type: journey
title: "Eleven gates green, six ADRs, and the Ising weights that needed a repo clone"
date: 2026-04-26
tags: [L4-orchestration, phase-0, smoke-tests, learnings]
related:
  - adr/0003-cuda-quantum-container
  - adr/0004-decomposer-llm-gemma4
  - adr/0006-pymatching-stim-native
  - adr/0007-nvidia-ising-predecoder
  - adr/0008-crumble-via-stim-svg
  - adr/0009-visualization-stack
one_line: "Phase 0 verified the substrate: all eleven smoke tests pass, CUDA-Q runs containerized with driver 535, Gemma 4 31B wins the decomposer bench at 100% JSON validity, and the Ising predecoder required cloning NVIDIA's inference repo rather than finding it inside the CUDA-Q container."
---

Phase 0 verified the substrate: container execution, model weights, dependency installation, and eleven smoke tests. The details of how each piece integrates were different enough from the plan that six ADRs needed writing.

## The eleven gates

Six numerical, five visualization. All pass in 8.6 seconds:

| Test | Target | Actual |
|------|--------|--------|
| 12-qubit QAOA (CUDA-Q container) | <5 s | 2.89 s |
| 28-qubit QAOA (cuStateVec) | <60 s | 18.76 s |
| Stim distance-5 syndrome at p=1e-3 | <2 s | 0.01 s |
| NVIDIA Ising predecoder forward pass | <50 ms | 8 ms |
| PyMatching decode | <200 ms | 15 ms |
| Postgres connectivity | connect | success |
| Stim SVG export | renders | success |
| PyMatching graph draw | renders | success |
| D-Wave inspector QUBO encoding | no phone-home | verified |
| QuTiP Bloch sphere | renders | success |
| npm install (dashboard deps) | <60 s | 29 s |

The comfortable margins on most tests are reassuring — the hardware has headroom. The 28-qubit QAOA at 18.76 s leaves room for d=7 surface codes with multiple rounds in Phase 1.

## CUDA-Q: container path confirmed

The host driver is 535.288.01 (CUDA 12.2 era). NVIDIA publishes `nvcr.io/nvidia/quantum/cuda-quantum:cu12-0.9.1`, which runs cleanly via `docker run --gpus all` with no driver touch. The smoke test bind-mounts a Python snippet, runs it inside the container, and captures stdout. Cold container start adds ~2 seconds; acceptable for demo flows.

The alternative — native pip install of `cuda-quantum` wheels — would require matching cuQuantum SDK and driver versions. The container isolates that coupling. ADR-0003 documents.

## The Ising predecoder required a repo clone

The planning assumption was that NVIDIA Ising Decoding weights would load via some `cudaq_qec` module inside the CUDA-Q container. That module does not exist in the cu12-0.9.1 image. The actual integration path:

1. Download weights from HuggingFace (`nvidia/Ising-Decoder-SurfaceCode-1-Fast`)
2. Clone `NVIDIA/Ising-Decoding` repo to `/data/models/nvidia-ising/Ising-Decoding/`
3. Use the repo's `safetensors_utils.load_safetensors()` to load the model
4. Run inference via standalone PyTorch 2.5.1+cu121 on the host

The forward pass is fast — 8 ms for a (1, 4, 9, 9, 9) tensor on GPU0. The weights are small: 1.8 MB for the speed variant (model_id=1, receptive field R=9). The code path is clean once you know it exists. ADR-0007 documents.

The lesson: NVIDIA's Ising ecosystem is split between the HuggingFace model cards (weights + metadata), the GitHub repo (inference code), and the future CUDA-Q QEC integration (not yet shipped). Phase 0 found the seam.

## Decomposer bench: Gemma 4 wins, but 80% schema compliance on compound asks

Five models benchmarked against a fixed five-prompt suite:

| Model | JSON valid | Schema OK | Median latency |
|-------|------------|-----------|----------------|
| `gemma4:31b-it-q8_0` | 100% | 80% | 16.56 s |
| `gemma4:26b` | 60% | 40% | 7.94 s |
| `nemotron-3-nano:30b` | 80% | 80% | 3.70 s |
| `gpt-oss:20b` | 80% | 80% | 2.95 s |
| `mistral-small3.2:latest` | 100% | 60% | 1.88 s |

Gemma 4 31B is the only model at 100% JSON validity with >=80% schema compliance. The 80% schema figure reflects failure on the compound multi-step ask (qec_syndrome + assignment in sequence) — it produced a single leaf instead of a two-node DAG. Single-leaf asks pass at 100%.

Mistral is 6× faster but misclassified the routing prompt as assignment. Nemotron and gpt-oss hit 80% JSON validity — retry logic would be needed. Gemma 4 is the path of least code.

ADR-0004 locks the choice. Phase 1 can revisit if compound decomposition becomes load-bearing.

## Visualization stack: all libraries work, Crumble deferred

The planning question was whether to iframe-embed Gidney's Crumble editor or just use Stim's native SVG export. After reading the Crumble source, the answer is clear: Stim's `circuit.diagram("svg")` produces exactly the lattice and detector visualizations we need. Crumble adds interactive editing we don't require in Phase 0. ADR-0008 documents.

The rest of the stack installed cleanly:

- **Stim** — SVG circuit diagrams with detector annotations
- **PyMatching** — `draw()` renders matching graphs (matplotlib backend, PNG output)
- **D-Wave inspector** — QUBO graph encoding works in offline mode; verified it does not phone home to D-Wave Leap
- **QuTiP** — Bloch sphere renders to PNG via matplotlib
- **Dashboard deps** — `@xyflow/react`, `recharts`, `deck.gl`, `plotly.js-basic-dist`, `@react-three/fiber`, `@react-three/drei` all install clean in 29 seconds

ADR-0009 documents the stack, including the deferred Crumble decision.

## PyMatching + Stim: native pip, not container

Both install cleanly into the host venv. No container needed. The integration is straightforward:

```python
import stim
import pymatching

circuit = stim.Circuit.generated("surface_code:rotated_memory_x", distance=5, rounds=5, ...)
dem = circuit.detector_error_model()
matching = pymatching.Matching.from_detector_error_model(dem)
correction = matching.decode(syndrome)
```

ADR-0006 documents. The API surface is stable — PyMatching 2.x matches the documented examples.

## What Phase 0 verified

1. **The container path works.** CUDA-Q runs with driver 535 via container forward-compat. No host driver changes needed.

2. **The Ising predecoder is standalone.** Not inside CUDA-Q; requires the GitHub repo and PyTorch. Integration path is documented; the forward pass is fast.

3. **Gemma 4 is the Decomposer.** 100% JSON validity matters more than latency for Phase 0. Compound decomposition is a known gap.

4. **Visualization is first-class.** All five viz libraries work. Stim SVG replaces any need for standalone Crumble.

5. **Postgres tenancy works.** `quantum_ai_orchestrator` database exists in supabase-db with five schemas migrated.

## What Phase 1 needs to prove

- The six pipeline modules (`decomposer.py` through `reassembler.py`) execute end-to-end
- Three decoders race on the same syndrome stream, LER diverges visibly
- Four optimization backends race on a QUBO, timings and quality visible in the dashboard
- Provenance rows land in Postgres; bi-temporal queries return sensible results
- The dashboard renders Problem Graph, Backend Bake-off, QEC Lab, and QUBO Graph panels

The substrate is verified. The architecture is scaffolded. Phase 1 is the first real workload.

## Related

- [ADR-0003](../../adr/0003-cuda-quantum-container.md) — CUDA-Q containerized execution
- [ADR-0004](../../adr/0004-decomposer-llm-gemma4.md) — Gemma 4 31B as Decomposer
- [ADR-0006](../../adr/0006-pymatching-stim-native.md) — PyMatching + Stim native pip
- [ADR-0007](../../adr/0007-nvidia-ising-predecoder.md) — NVIDIA Ising predecoder integration
- [ADR-0008](../../adr/0008-crumble-via-stim-svg.md) — Stim SVG instead of Crumble
- [ADR-0009](../../adr/0009-visualization-stack.md) — Visualization stack decisions
