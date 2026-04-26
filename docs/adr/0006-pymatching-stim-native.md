# ADR-0006: PyMatching and Stim as native pip dependencies

- **Status:** Accepted
- **Date:** 2026-04-26
- **Deciders:** rollik

## Context

The QEC decode skill requires two libraries:

1. **Stim** — generates surface-code circuits and samples syndrome data from detector error models (DEMs).
2. **PyMatching** — minimum-weight perfect matching (MWPM) decoder that consumes Stim's DEM format.

Both are maintained by Google Quantum AI (Craig Gidney). The question is whether to containerize them (like CUDA-Q) or install natively in the host venv.

## Decision

Install **Stim 1.15** and **PyMatching 2.3** as native pip dependencies in the host venv (`pyproject.toml`).

```toml
dependencies = [
    "stim>=1.15,<2",
    "pymatching>=2.3,<3",
    ...
]
```

No container required. Both libraries are pure Python with prebuilt wheels for Linux x86_64 / Python 3.11.

## Alternatives considered

- **Containerize inside cuda-quantum** — CUDA-Q images include cuQuantum but not Stim/PyMatching. We'd need a custom Dockerfile layering them in. This adds build complexity and defeats the "use official images" principle from ADR-0003.

- **Separate Stim container** — Stim has no GPU dependency. Containerizing a pure-Python library adds IPC overhead for no benefit.

- **Use NVIDIA's Ising predecoder instead of PyMatching** — The Ising predecoder (ADR-0007) is a *complement* to PyMatching, not a replacement. It outputs soft information that feeds into PyMatching's MWPM stage. We need both.

## Consequences

### Positive

- `uv pip install` pulls prebuilt wheels in <10 s.
- Direct Python imports — no subprocess or container spin-up.
- Stim's `stim.Circuit.diagram("svg")` works natively for visualization (test 07).
- PyMatching's `pymatching.draw()` works natively (test 08).
- Smoke tests 03, 05, 07, 08 all pass without containers.

### Negative / accepted trade-offs

- Version drift between Stim and PyMatching can cause API mismatches. We pin both in `pyproject.toml` and upgrade together.
- Stim's C++ core is compiled into the wheel; no GPU acceleration. For Phase-0 scales (d≤17), CPU is sufficient.

## References

- Stim GitHub: https://github.com/quantumlib/Stim
- PyMatching GitHub: https://github.com/oscarhiggott/PyMatching
- Stim + PyMatching tutorial: https://github.com/quantumlib/Stim/blob/main/doc/getting_started.ipynb
