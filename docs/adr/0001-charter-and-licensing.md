# ADR-0001: Project charter and licensing posture

- **Status:** Accepted
- **Date:** 2026-04-26
- **Deciders:** Ken Rollins

## Context

`quantum-ai-orchestrator` is a public, customer-shareable demonstration of an AI-orchestrated control plane for hybrid quantum-classical workloads, built specifically as an AI + quantum talk track and demo for Dell Federal. Three things have to be locked before any code lands:

1. **What's in scope and what isn't** — the project is a workload orchestrator above existing quantum runtimes (CUDA-Q), not a runtime substrate, not a calibration product, not an SDK.
2. **Code license** — must be compatible with our key dependencies (NVIDIA Ising, Stim, PyMatching, CUDA-Q ecosystem, dwave-inspector, Crumble, Quirk — all Apache 2.0; QuTiP BSD-3; r3f / deck.gl / Plotly.js / Recharts MIT).
3. **Data and model handling** — what we ship in the repo, what we pull at runtime, what we never commit. Federal sensitivity matters even for this demo because the talk-track audience reviews on-prem and air-gapped postures.

## Decision

- **Code license: Apache 2.0.** Most-compatible choice for our dependency graph. Matches NVIDIA Ising's license terms and the broader CUDA-Q ecosystem. No copyleft surprises for downstream users.
- **Repo posture: public from day one.** The README is part of Phase 0, not a final-polish item. The journey artifact (`docs/journal/journey/`) is part of the public surface and has to read as honest engineering at every step.
- **No `dell-` prefix in the repo name.** Avoids brand and trademark friction. The README does the Dell positioning explicitly; the artifact name stays brand-safe.
- **Models are pulled at first run, never committed.** NVIDIA Ising Decoding weights live at `/data/models/nvidia-ising/` (out of repo). `tools/bootstrap_ising.sh` handles the pull. Weights are open-source per NVIDIA's terms but we do not redistribute them.
- **Demo data is fetched, not committed.** yfinance data for the `portfolio` skill (Phase 3) is pulled by a fetch script. No CSVs in the repo.
- **Credentials hygiene.** `/data/docker/supabase/.env` on the host contains many secrets we don't need (Langfuse keys, JWT secret, dashboard password). The project's `.env` (gitignored) contains *only* the Postgres credentials we need: `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`. The bootstrap script extracts only those keys.

## Alternatives considered

- **MIT or BSD-3 license.** Both are simpler than Apache 2.0 but lack the explicit patent grant. Apache 2.0 is the consensus in the quantum-software ecosystem we plug into; using a different license would require justifying mismatch on every dependency interaction. Rejected.
- **GPL or LGPL.** Copyleft propagates into anyone who builds on the orchestrator. We want the project to be *adopted*, not avoided by enterprise integrators. Rejected.
- **`dell-quantum-orchestrator` or similar Dell-prefixed name.** Strongest sales angle but creates trademark questions on a personal GitHub account. Cleaner to position via README and have the repo name be brand-safe. See planning session for the full naming traceback (Conductor Quantum collision avoided, "ai-quantum-conductor" considered, then dropped in favor of "orchestrator" once "conductor" was killed).
- **Private repo until Phase 2.** Slower flywheel; no public artifact for SE-shareable demos until late. Rejected — the journey is more valuable when it accumulates publicly. Risk mitigations: Dell brand check before any journey entry that names Dell directly; never commit `.env`.

## Consequences

### Positive

- License compatibility across the entire dependency graph is automatic.
- Public-from-day-one means the journal compounds in value as the project progresses.
- Brand-safe repo name means we don't have to fight a brand-review process to ship Phase 0.
- Tight credential scope (only Postgres values from supabase `.env`) limits blast radius if the project `.env` is ever leaked.

### Negative / accepted trade-offs

- Apache 2.0 is more verbose than MIT — every source file should ideally carry a license header (deferred to Phase 1 polish).
- Public-from-day-one means we have to be careful with any Dell brand references in journey entries — adds a brand-check step before publish.
- Pulling Ising weights at first run rather than committing them means CI has to download ~16 GB to run smoke tests. Trade for license cleanliness.

## References

- NVIDIA Ising launch: https://nvidianews.nvidia.com/news/nvidia-launches-ising-the-worlds-first-open-ai-models-to-accelerate-the-path-to-useful-quantum-computers
- NVIDIA Ising tech blog: https://developer.nvidia.com/blog/nvidia-ising-introduces-ai-powered-workflows-to-build-fault-tolerant-quantum-systems/
- Apache License 2.0: https://www.apache.org/licenses/LICENSE-2.0
- Conductor Quantum (the naming collision): https://www.conductorquantum.com/
- Plan: [`../plan.md`](../plan.md), §1, §11 (risks 5, 6, 11)
