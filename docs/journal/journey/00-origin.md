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

The planning assumption was NVLink between the two cards. The previous-generation RTX A6000 supported it via an optional bridge; the workstation's cards do not. The recon was unambiguous:

```
$ nvidia-smi nvlink --status        # empty output
$ nvidia-smi nvlink --capabilities  # empty output
$ nvidia-smi topo -m
       GPU0  GPU1  CPU Affinity ...
GPU0   X     SYS   ...
GPU1   SYS   X     ...
```

`SYS` indicates the link traverses PCIe and the NUMA interconnect. NVIDIA's datasheet confirms what the topology output suggests: NVLink was removed from the Ada-generation workstation silicon entirely. There is no bridge to add.

The architectural consequence is a pivot from VRAM pooling to per-GPU lane assignment. Each GPU-bound backend runs on its own card; the dispatcher assigns lanes; both GPUs run different backends concurrently. Multi-GPU statevector simulation caps at roughly 30 qubits on a single 48 GB card rather than the ~33 we'd hoped for from pooling. PCIe peer-to-peer without NVLink would buy back a couple of qubits at the cost of significant orchestration complexity and roughly an order of magnitude lower bandwidth than NVLink would have provided. Not worth it.

!!! quote ""
    Two GPUs racing two backends, each in its own lane, is the literal visual of hybrid orchestration. Memory pooling would have been less honest.

The Backend Bake-off panel in the dashboard becomes what it claims to be: parallel races on visibly distinct hardware. ADR-0002 documents the decision and the alternatives considered (PCIe pooling, cuTensorNet over host RAM, an NVLink-equipped workstation that doesn't exist in the Ada generation).

## The work decomposes into a pipeline of six stages

A natural-language ask becomes a problem-graph DAG via a Decomposer (Gemma 4 31B with JSON-schema-constrained output). Each leaf goes to a skill-specific Formulator that emits a backend-ready input — a QUBO matrix, an Ising J/h pair, a syndrome tensor. A Dispatcher picks one or more backends per leaf from a registry, weighted by a learned-preference table in Postgres. Backends run in parallel, possibly across both GPUs and the CPU. An Evaluator scores each result for quality, wall time, and a domain-specific metric (logical error rate for QEC; objective-vs-LP-bound for optimization). A Reassembler walks the DAG bottom-up to build the parent answer. Every decision lands in a Postgres provenance log.

Each ask is one pass through the six stages — Decomposer, Formulator, Dispatcher, backends, Evaluator, Reassembler. No rollback, no mid-task retries. A backend losing the race is not a failure; it is data. A Strategist process (Phase 2) reads outcomes between asks and updates the preference table, so the orchestrator learns which backends suit which problem fingerprints over time. Learning happens between asks, not within.

!!! quote ""
    Six modules, one pass, scored outcomes. The architecture optimizes for observability and audit, not for mid-task recovery.

## Postgres handles the provenance store

The audit story is the technical-credibility story. A reasonable question from a federal evaluator or any technical reader is: *as of last Tuesday, why did we send distance-5 surface codes at p=5e-3 to the accuracy-variant decoder?* The answer has to read in something they already speak.

Per ask, the orchestrator records on the order of tens of rows: one in `runs`, a small DAG in `problem_graphs`, one row per dispatched backend in `dispatches` and `outcomes`, occasionally a new row in `lessons`. There is no vector retrieval, no fulltext index over reflections, no traversal over thousands of nodes. There is bi-temporal querying — `valid_from` / `valid_to` columns answer the as-of question — and recursive ancestry traversal via a CTE over the problem graph. Plain Postgres handles both.

The workstation already runs a self-hosted Supabase stack. We become a tenant: one new database (`quantum_ai_orchestrator`), per-skill schemas inside it (`common`, `qec_decode`, `mission_assignment`, `routing`, `portfolio`), connection via the supavisor pooler at `localhost:5432`. No new infrastructure to manage. Standard tools — Grafana, Metabase, psql — work day-1. ADR-0005 documents the decision and the alternatives considered (Apache AGE for Cypher-on-Postgres if the dashboard graph viz benefits in Phase 3; a standalone Postgres container; DuckDB for offline replay).

## The Decomposer is Gemma 4 31B, validated rather than narrative-aligned

There is a federal-narrative argument for an NVIDIA-branded LLM at the orchestration layer: Nemotron Super reads as *NVIDIA throughout the stack*. The argument loses on two counts. First, NVIDIA is already throughout the *quantum* stack — Ising, CUDA-Q, cuStateVec, NVQLink — so an NVIDIA-branded Decomposer is gravy, not load-bearing. Second, we have prior hands-on validation of `gemma4:31b-it-q8_0` for tool use and JSON-schema-constrained output. Apache 2.0 weights also avoid the friction of the NVIDIA Open Model License for a public repo.

Phase 0 still benches Kimi K2.6, DeepSeek-R1, and Nemotron Super on a fixed prompt suite as a sanity check. Gemma 4 31B is the incumbent. ADR-0004 will lock or break the tie based on actual numbers from `tools/bench_decomposers.sh`.

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
