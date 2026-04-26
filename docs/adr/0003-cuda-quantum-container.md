# ADR-0003: CUDA-Q execution via container, not host install

- **Status:** Accepted
- **Date:** 2026-04-26
- **Deciders:** rollik

## Context

CUDA-Q (nvidia/cuda-quantum) is the primary statevector simulator for Phase-0 QAOA gates. It requires a specific CUDA driver/runtime pairing and ships Python bindings tied to the container's Python. Installing CUDA-Q natively would:

1. Pin the host Python to the container's Python version (currently 3.11).
2. Require driver version alignment — the workstation runs 535.288.01, which is forward-compatible but not necessarily the version CUDA-Q links against.
3. Add ~15 GB of CUDA libraries to the host venv.

Federal deployments will run on heterogeneous hardware. Containerizing CUDA-Q isolates the driver/runtime coupling.

## Decision

Run all CUDA-Q workloads inside the official container:

```
nvcr.io/nvidia/quantum/cuda-quantum:cu12-0.9.1
```

The host venv (`uv venv --python 3.11`) carries orchestration code only. Smoke tests spin up the container via `docker run --gpus all`, bind-mount a snippet file, and capture stdout.

NGC authentication is required (gated images). The NVIDIA_API_KEY from `~/.bashrc` is used for `docker login nvcr.io`.

## Alternatives considered

- **Native pip install of cuda-quantum wheels** — NVIDIA provides wheels, but they assume a matching cuQuantum SDK and driver. On this workstation with driver 535 and no cuQuantum native install, the container is cleaner. The Phase-1 CI matrix would need to replicate this pairing for every runner.

- **Host CUDA 12.x native install + cuQuantum** — Adds 20+ GB and couples the host to a specific CUDA version. We'd lose the ability to test different CUDA-Q releases in parallel lanes.

- **Multi-stage Docker build embedding our orchestrator** — Considered for production, but Phase-0 is about proving the solvers work. The bind-mount pattern keeps iteration fast.

## Consequences

### Positive

- CUDA driver forward-compat (535) works out of the box with CUDA 12.x containers.
- Smoke tests verify real container behavior, not a local approximation.
- Upgrading CUDA-Q is a one-line image tag change.
- Both RTX 6000 Ada GPUs are visible inside the container (`--gpus all`).

### Negative / accepted trade-offs

- Container cold-start adds ~2 s to test wall time. Acceptable for Phase-0.
- Debugging CUDA-Q internals requires exec-ing into the container.
- The orchestrator cannot import cudaq directly; inter-process communication is via subprocess + JSON.

## References

- NVIDIA NGC CUDA-Q: https://catalog.ngc.nvidia.com/orgs/nvidia/containers/cuda-quantum
- cudaq.kernel requires source file: https://nvidia.github.io/cuda-quantum/latest/using/cudaq.html#kernel-decorator
- Driver 535 forward-compat matrix: https://docs.nvidia.com/deploy/cuda-compatibility/
