# quantum-ai-orchestrator

An AI-orchestrated control plane for hybrid quantum-classical workloads. Takes a natural-language ask, decomposes it via a local LLM into a problem graph, dispatches each leaf in parallel across a portfolio of GPU-backed solvers (classical, quantum-inspired annealing, GPU statevector simulation, AI quantum-error-correction decoders), races them, picks the winner, reassembles the answer, and records every decision in an auditable Postgres provenance log. The substrate today is GPUs; the pipeline is designed so QPU backends slot in unchanged when they arrive.

## What's in scope

Phase 1 ships two skills end-to-end:

- **`qec_decode`** — simulates a noisy logical qubit with [Stim](https://github.com/quantumlib/Stim), races [NVIDIA Ising Decoding](https://nvidianews.nvidia.com/news/nvidia-launches-ising-the-worlds-first-open-ai-models-to-accelerate-the-path-to-useful-quantum-computers) (speed and accuracy variants) against [PyMatching](https://github.com/oscarhiggott/PyMatching) on the same syndrome stream, and shows the logical-error-rate divergence live.
- **`mission_assignment`** — formulates an asset-to-task assignment as a QUBO and dispatches it across classical (OR-Tools), simulated annealing (dwave-neal), and GPU QAOA (CUDA-Q) backends in parallel.

Phase 2 adds vehicle routing; Phase 3 adds Markowitz portfolio optimization. The pipeline architecture handles all four problem classes from day one — only the per-skill formulator/evaluator code lands per phase.

## Why this exists

Useful quantum computing is a 2030s problem. The *operating model* for hybrid AI-quantum workloads is a today problem. This project demonstrates an answer: an open-source pipeline that runs end-to-end on a single Dell workstation with two NVIDIA RTX 6000 Ada GPUs, no QPU required. Every dispatch decision and outcome is recorded in a Postgres audit log — bi-temporal, queryable in plain SQL by anyone who wants to audit the decisions.

The strategic anchor is NVIDIA's [Ising open-model family](https://developer.nvidia.com/blog/nvidia-ising-introduces-ai-powered-workflows-to-build-fault-tolerant-quantum-systems/), released April 14, 2026. Ising Decoding is reportedly 2.5× faster and 3× more accurate than traditional decoders. We integrate it as a backend and race it live; the demo makes that improvement visible, not just claimed.

## How this is *not* a competitor to existing work

- We are **not** a quantum runtime — [NVIDIA CUDA-Q](https://developer.nvidia.com/cuda-q) is, and we sit above it.
- We are **not** a calibration product — [Conductor Quantum](https://www.conductorquantum.com/) and others operate at the QPU calibration layer; we operate at the workload-orchestration layer above CUDA-Q.
- We are **not** a quantum SDK — Qiskit, Cirq, PennyLane, and CUDA-Q are; we use them.

We are the thin AI layer that takes natural-language asks, decides which solver gets which work, and proves the choice with provenance. When real QPUs arrive, they slot into the backend registry like any other accelerator.

## Status

In active development. The implementation plan is at [`docs/plan.md`](docs/plan.md). The build journal — written predicament-first, in the style of Dan Luu / Andy Weir / Matt Levine — is at [`docs/journal/journey/`](docs/journal/journey/). Architectural decisions are recorded in [`docs/adr/`](docs/adr/).

## Quick start

```bash
# After Phase 0 bootstrap (see docs/plan.md §14):
cd /data/code/quantum-ai-orchestrator
uv venv --python 3.11
uv pip install -e .[dev]
make smoke      # runs the 11 Phase-0 gate tests
make demo       # end-to-end qec_decode demo (Phase 1)
```

## License

Apache 2.0. Same license family as our key dependencies (NVIDIA Ising, Stim, PyMatching, CUDA-Q, dwave-inspector, Quirk, Crumble).
