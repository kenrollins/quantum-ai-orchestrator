---
id: journey-00-origin
type: journey
title: "No QPU, no NVLink, an AI decoder NVIDIA released twelve days ago"
date: 2026-04-26
tags: [L4-orchestration, project-charter, decision]
related:
  - adr/0001-charter-and-licensing
  - adr/0002-no-nvlink-two-gpu-racing
  - adr/0005-postgres-tenant-no-neo4j
one_line: "An AI-orchestrated control plane for hybrid quantum-classical workloads, built on a single workstation: the substrate (no QPU, two PCIe-only RTX 6000 Adas, an open AI decoder fresh from NVIDIA, an existing Supabase tenancy, a local Gemma 4 31B) shaped every architectural decision in Phase 0."
---

Useful, fault-tolerant quantum computing is roughly a 2030s problem. The *operating model* for the hybrid AI-quantum workloads that lead up to it — natural-language ask in, the right solver picked from a portfolio of classical, quantum-inspired, and quantum-simulator backends, every decision recorded for audit — is a today problem. The thesis of this project is that the operating model can be built end-to-end on hardware that exists right now, and that when QPUs arrive they slot into a backend registry like any other accelerator.

The substrate is a single Dell Precision 7960 workstation with two NVIDIA RTX 6000 Ada GPUs, a Xeon w9-3495X with AMX, 502 GiB of RAM, an existing self-hosted Supabase stack at `/data/docker/supabase/`, and an Ollama daemon already serving `gemma4:31b-it-q8_0`. The strategic anchor is NVIDIA's open Ising model family, released on World Quantum Day (2026-04-14) — twelve days before this entry — which ships an AI quantum-error-correction decoder reportedly 2.5× faster and 3× more accurate than traditional decoders. The Phase 0 demo is to race that decoder live against PyMatching on Stim-generated surface-code syndromes, on the GPUs we have, and to record every decision in Postgres.

Phase 0 is a recon-and-scaffold pass. Five findings against the substrate, and what each one did to the architecture, follow.

## The two GPUs do not have NVLink

The RTX 6000 Ada Generation does not include NVLink — NVIDIA removed it from the Ada-generation workstation silicon. The two GPUs communicate only via PCIe:

```
$ nvidia-smi topo -m
        GPU0    GPU1    CPU Affinity    NUMA Affinity
GPU0     X      SYS     0-111           0
GPU1    SYS     X       0-111           0
```

`SYS` indicates the link traverses PCIe and the NUMA interconnect. Multi-GPU statevector simulation caps at roughly 30 qubits on a single 48 GB card.

The architecture assigns each GPU-bound backend to its own card. The dispatcher picks lanes; both GPUs run different backends concurrently. The Backend Bake-off panel shows parallel races on distinct hardware. ADR-0002 documents the decision.

## Natural language as the interface

The gap between "I need to decode a surface code at this noise rate" and "here is a syndrome tensor formatted for this specific decoder" is exactly the kind of translation an LLM handles well. The orchestrator accepts natural-language asks and uses an LLM (Gemma 4 31B) to decompose them into a typed problem graph. This serves two purposes: it lowers the barrier for exploring what the system can do, and it produces a structured representation that the rest of the pipeline can act on deterministically.

The Decomposer emits JSON conforming to a fixed schema. Downstream stages — Formulator, Dispatcher, backends, Evaluator, Reassembler — are pure functions over that structure. The LLM handles ambiguity at the top; everything below it is typed and auditable.

## The pipeline has six stages

Each ask is one pass through six stages:

1. **Decomposer** — LLM converts natural language to a problem-graph DAG
2. **Formulator** — each leaf becomes a backend-ready input (QUBO matrix, Ising J/h, syndrome tensor)
3. **Dispatcher** — picks backends from a registry, weighted by a learned-preference table
4. **Backends** — run in parallel across GPUs and CPU
5. **Evaluator** — scores each result for quality, wall time, and domain-specific metrics
6. **Reassembler** — walks the DAG bottom-up to build the final answer

Every decision lands in a Postgres provenance log. A backend losing the race is not a failure; it is data. A Strategist process (Phase 2) reads outcomes between asks and updates the preference table, so the orchestrator learns which backends suit which problem fingerprints over time.

## Postgres handles the provenance store

When AI makes decisions — which decoder to use, which backend won the race — the reasoning should be queryable after the fact. The orchestrator records every dispatch and outcome in Postgres with bi-temporal columns (`valid_from` / `valid_to`). A query like "what was the preferred backend for distance-5 codes at p=5e-3 as of last Tuesday" is a plain SQL WHERE clause.

Per ask, the orchestrator writes tens of rows: one in `runs`, a small DAG in `problem_graphs`, one row per dispatched backend in `dispatches` and `outcomes`, occasionally a new row in `lessons`. Recursive CTEs traverse problem-graph ancestry. Plain Postgres handles both patterns.

The workstation already runs a self-hosted Supabase stack. We become a tenant: one new database (`quantum_ai_orchestrator`), per-skill schemas inside it. ADR-0005 documents the decision.

## Gemma 4 31B as the Decomposer

The Decomposer needs to emit valid JSON conforming to a fixed schema, every time. `gemma4:31b-it-q8_0` has prior validation for tool use and JSON-constrained output. It runs locally on Ollama, fits in ~34 GB VRAM (leaving headroom on the 48 GB cards), and is Apache 2.0 licensed.

Phase 0 benchmarks five candidate models on a fixed prompt suite covering all four problem classes. ADR-0004 documents the results — Gemma 4 was the only model at 100% JSON validity with ≥80% schema compliance.

## The visualization stack is load-bearing

Quantum demos die on visuals. The decision is to treat visualization as a first-class deliverable and to verify each library can be installed and called once before any pipeline code lands.

Stim does dual duty as syndrome generator (backend) and SVG diagrammer — `Circuit.diagram()` produces lattice and circuit views we embed directly in the QEC Lab panel. PyMatching exposes `matching.draw()` for the matching-graph visual. D-Wave's problem-inspector renders Ising/QUBO graphs natively, including chimera and pegasus topology with state heatmaps. QuTiP generates Bloch spheres server-side as PNG snapshots, streamed over SSE when needed. react-three-fiber + drei handles live 3D for custom Bloch / spin-lattice / energy-landscape views in the Quantum Visualizer panel. deck.gl draws routing maps in Phase 2; Plotly.js draws the efficient frontier in Phase 3. Recharts and React Flow + Dagre carry the time-series and DAG-layout views.

Phase 0 includes five visualization smoke renders alongside the six numerical gates. If a library cannot be installed and produce output once on this host, that is a Phase-0 finding, not a mid-Phase-1 surprise. ADR-0009 will document the stack, including the still-open Crumble integration question (iframe-embed Gidney's Crumble itself versus port the visual idiom into our own SVG render). That decision is deferred to Phase 1 once the QEC Lab panel exists in skeleton form, and is also gated on whether Crumble can be self-hosted cleanly — running it from `algassert.com` would leak demo activity to a third-party server and would not work in any air-gapped environment.

## Phase 0 verifies eleven gates before Phase 1 begins

Six numerical: 12-qubit Max-Cut QAOA on CUDA-Q under 5 s on one card; 28-qubit QAOA via cuStateVec under 60 s; Stim distance-5 surface-code syndrome stream at p=1e-3 under 2 s; NVIDIA Ising Decoding inference on that syndrome under 50 ms; PyMatching baseline decode under 200 ms; `psycopg.connect()` to `quantum_ai_orchestrator` via the supavisor pooler succeeds.

Five visualization: `stim.Circuit.generated(...).diagram()` produces SVG; `pymatching.Matching(...).draw()` renders; `dwave.inspector.show(...)` opens a viewer (and verifiably does not phone home to D-Wave Leap); `qutip.Bloch().render()` produces matplotlib output; the dashboard's `npm install` of viz dependencies completes clean.

If any gate fails, Phase 0 halts and an ADR documents the gap before Phase 1 work begins. ADRs 0003 (containerized CUDA-Q, since the host driver is 535.288.01 and we want CUDA 12.5+ runtime without touching the driver), 0004 (Decomposer choice), 0006 (Stim + PyMatching API integration), 0008 (Crumble integration mode), 0009 (visualization stack), and 0010 (Python-version fallback if 3.11 wheels are unavailable for any pinned dependency) will land as the actual environment confirms or refutes the planning assumptions.

Phase 1 is two skills end-to-end. `qec_decode` races NVIDIA Ising's speed and accuracy variants against PyMatching on Stim syndromes — the hero demo for *AI making quantum reliable today*. `mission_assignment` formulates a weighted-assignment QUBO and dispatches it across four backends in parallel — the orchestration thesis on a clean, abstract optimization problem. One demo, two acts, three minutes end-to-end on the workstation.

## Related

- [ADR-0001](../../adr/0001-charter-and-licensing.md) — project charter and Apache 2.0 licensing posture for code, models, and data
- [ADR-0002](../../adr/0002-no-nvlink-two-gpu-racing.md) — no-NVLink reality and the two-GPU racing pivot
- [ADR-0005](../../adr/0005-postgres-tenant-no-neo4j.md) — Postgres tenancy of the existing Supabase, no graph database in Phase 1–2
- [`docs/plan.md`](../../plan.md) — the canonical implementation plan
