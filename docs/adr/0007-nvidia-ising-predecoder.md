# ADR-0007: NVIDIA Ising Predecoder as soft-information stage

- **Status:** Accepted
- **Date:** 2026-04-26
- **Deciders:** rollik

## Context

NVIDIA released open weights for their Ising Decoding system — a 3D-CNN predecoder that processes surface-code syndrome volumes and outputs soft information for downstream MWPM decoders. The system is described in their GTC 2025 talk and published on HuggingFace:

- `nvidia/Ising-Decoder-SurfaceCode-1-Fast` (model_id=1, R=9, ~1.8 MB FP16)
- `nvidia/Ising-Decoder-SurfaceCode-1-Accurate` (model_id=4, R=13, ~3.5 MB FP16)

The inference code is in the `NVIDIA/Ising-Decoding` GitHub repo.

## Decision

Use the NVIDIA Ising predecoder as an **optional soft-information stage** ahead of PyMatching. The pipeline becomes:

```
Stim DEM → syndrome tensor → Ising predecoder → soft info → PyMatching MWPM → correction
```

Key integration points:

1. Weights are downloaded via `tools/bootstrap_ising.sh` to `/data/models/nvidia-ising/`.
2. The inference repo is cloned to `/data/models/nvidia-ising/Ising-Decoding/`.
3. PyTorch 2.5.1+cu121 is installed in the host venv for GPU inference.
4. The predecoder forward pass runs on GPU0; PyMatching runs on CPU.

Smoke test 04 validates the forward pass completes in <50 ms.

## Alternatives considered

- **Skip the predecoder, use PyMatching alone** — Works fine for d≤13, but the predecoder improves logical error rate (LER) at scale. We want the option for Phase-1 benchmarking.

- **Run predecoder inside a TensorRT container** — The Ising-Decoding repo supports TensorRT workflows, but the PyTorch path is simpler for Phase-0. TensorRT adds 15 GB+ of dependencies and ONNX export complexity.

- **Wait for cudaq_qec integration** — NVIDIA may ship the predecoder inside future CUDA-Q QEC releases. We can switch then; for now, the standalone PyTorch path works.

## Consequences

### Positive

- Forward pass is fast: <5 ms on RTX 6000 Ada for d=9 batch=1.
- Weights are small (1.8–3.5 MB), trivial to redistribute.
- The predecoder is Apache-2.0 licensed (the *code*; weights are NVIDIA Open Model License but allow research/demo use).
- Adds a differentiable stage for future hybrid classical-quantum training experiments.

### Negative / accepted trade-offs

- Weights are gated on HuggingFace (auto-approve click-through). First-time setup requires manual accept.
- The predecoder expects a specific syndrome tensor format (B, 4, T, D, D). Converting Stim output requires a formatting step.
- Two GPU-using components (predecoder + CUDA-Q) may need lane assignment to avoid VRAM contention. Phase-1 work.

## References

- HuggingFace model card: https://huggingface.co/nvidia/Ising-Decoder-SurfaceCode-1-Fast
- GitHub repo: https://github.com/NVIDIA/Ising-Decoding
- Weights license: NVIDIA Open Model License (see repo LICENSE file)
