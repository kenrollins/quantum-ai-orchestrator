---
id: journey-00-origin
type: journey
title: "Fourteen decisions, no QPU, two GPUs that don't talk to each other"
date: 2026-04-26
tags: [L4-orchestration, project-charter, decision]
related:
  - adr/0001-charter-and-licensing
  - adr/0002-no-nvlink-two-gpu-racing
  - adr/0005-postgres-tenant-no-neo4j
one_line: "Dell Federal needs an AI + quantum talk track; there is no QPU but there is GPU; the harness from gemma-forge does not fit; figuring out what fits instead took fourteen architectural decisions in a single planning session."
---

Dell Federal needs an AI + quantum talk track. There is no QPU. There is GPU. The harness from gemma-forge does not fit, and figuring out what fits instead took fourteen architectural decisions in one planning session.

The premise was clean enough: build a public, customer-shareable demo that shows hybrid AI + quantum on Dell hardware, journal it like gemma-forge, ride NVIDIA's brand-new Ising release as the federal hero ingredient. The premise survived. The architecture didn't.

## The first thing that broke was the inheritance

Gemma-forge's Ralph loop is a retry-and-reflect machine. An agent tries, fails, the Reflector distills a banned approach, the agent tries again with the lesson applied, eventually succeeds or escalates. It is the right shape for STIG remediation, where outcomes are categorical and learning compounds across runs.

It is not the shape of this project. There is no try-fail-reflect-retry. There is decompose-formulate-dispatch-race-evaluate-reassemble-record. That is a pipeline, not a loop.

!!! quote ""
    Backend losing the race ≠ failure.

The five Protocols carried the loop's assumptions. Two of them (Executor, Evaluator) survived. Three (WorkQueue, Checkpoint, WorkItem-as-retryable) reshaped or got cut. FailureMode went with them — we score outcomes, we don't categorize failures. So did Reflector and the banned-approaches semantic — we learn *positive* preferences (this backend wins for this problem class), not bans.


## The second thing that broke was Neo4j

Gemma-forge's memory stack is Graphiti-on-Neo4j plus Postgres for episodic state, with a dream pass between runs that consolidates lessons. It works because gemma-forge has agentic memory: vector retrieval over reflections, bi-temporal lessons indexed for fast lookup, audit traces over arbitrary subgraphs.

This project has ten to a hundred dispatch records per ask. Plain Postgres handles that. Bi-temporal `valid_from / valid_to` columns answer the audit query *"as of last Tuesday, why did we send distance-5 surface codes at p=5e-3 to ising_accuracy?"* in plain SQL. Federal evaluators read SQL faster than they read Cypher. Standard tools — Grafana, Metabase, psql — work day-1.

Dropping Graphiti was not the obvious call. It was the right call once we wrote the data we'd actually be storing. ADR-0005.

## The third thing that broke was the GPU topology

Kaiju has two RTX 6000 Ada Generation cards. We assumed NVLink because the previous-generation A6000 had it. The recon was definitive on two fronts. `nvidia-smi nvlink --status` returned empty output. NVIDIA's own datasheet for the RTX 6000 Ada is explicit: the Ada-generation workstation cards do not have NVLink. The connector is gone from the silicon.

Multi-GPU statevector simulation caps at ~30 qubits instead of the ~33 we'd hoped for. We considered fighting the constraint with cuTensorNet for tensor-network simulation across host RAM. Then we noticed the constraint was actually the demo:

!!! quote ""
    Two GPUs racing two backends, each in its own lane, is the literal visual of hybrid orchestration. Memory pooling would have been less honest.

The Backend Bake-off panel becomes what it claims to be — parallel races, not synthesized comparisons. ADR-0002.

## The fourth thing that broke was the Decomposer narrative

Ten minutes were spent arguing for `nemotron-3-super` as the Decomposer because *NVIDIA throughout the stack* read federal-friendly. Ken's pushback was a single sentence: he had hands-on validation of `gemma4:31b-it-q8_0` for tool use and JSON output. That ended the argument. NVIDIA is already throughout the *quantum* stack — Ising, CUDA-Q, cuStateVec, NVQLink. Putting an NVIDIA-branded LLM at the orchestration layer is gravy, not load-bearing. Validated beats narrative-aligned. Apache 2.0 weights also beat the NVIDIA Open Model License for a public repo.

Phase 0 still benches Kimi K2.6, DeepSeek-R1, and Nemotron Super against a fixed prompt suite as a sanity check. Gemma 4 31B is the incumbent. ADR-0004 will lock or break the tie.

## The fifth thing that broke was the name

`quantum-conductor` was almost the name. It captured the orchestration thesis cleanly. Then the collision check found Conductor Quantum — a Y Combinator-backed startup founded 2024, AI software for QPU calibration, NVIDIA Ising adopter, demo'd autonomous quantum labs with EeroQ on Ising decoding. Same federal-adjacent customer base. Hard kill on any `-conductor` variant.

The grammar question for `quantum-ai-conductor` versus `ai-quantum-conductor` resolved in favor of the latter (the project IS a quantum conductor, AI is how it's built — `ai-(quantum-conductor)`). Then the entire `-conductor` lane went away with the collision. The pivot landed at `quantum-ai-orchestrator` — drier, more honest, zero collision, and "orchestrator" covers all six pipeline stages, not just dispatch.

## The visualization stack is load-bearing

Every quantum demo dies on visuals. We made the choice early to treat visualization as a first-class deliverable, not a final-polish concern. Stim does dual duty as syndrome generator (backend) and SVG diagrammer. PyMatching exposes its own `matching.draw()`. D-Wave's problem-inspector renders Ising graphs natively. QuTiP generates Bloch spheres server-side. react-three-fiber + drei handles the live 3D. Phase 0 includes five visualization smoke renders alongside the six numerical gates — if a library can't be installed and called once, we find out in Phase 0, not in the middle of building the QEC Lab panel.

ADR-0009 will document each library's role and the Crumble iframe-versus-port decision deferred to Phase 1.

## What we are about to try

Phase 0 wraps the scaffold half on this Claude Code instance — repo created on GitHub, LICENSE, this journal entry, the plan, the ADR template, the `quantum_ai_orchestrator` Postgres database with five schemas migrated. Then a fresh Claude Code instance picks up on kaiju and runs the install half — venv, deps, container pull, Ising weights, the eleven smoke tests, the Decomposer bench. ADRs get written as the actual environment confirms or refutes the assumptions captured here.

Phase 1 is two skills end-to-end: `qec_decode` (NVIDIA Ising decoding versus PyMatching live, on Stim-generated syndromes) and `mission_assignment` (a weighted-assignment QUBO raced across four backends in parallel). One demo, two acts, three minutes.

The bet is that the journey reads honestly enough at every step to be useful to a technical reader who wants to understand how this was actually built. The bet is also that the first journal entry should land before the first commit of code, so the *why* is locked before the *what* obscures it. That is what entry 00 is for.

## Related

- [ADR-0001](../../adr/0001-charter-and-licensing.md) — project charter and Apache 2.0 / data / model licensing posture
- [ADR-0002](../../adr/0002-no-nvlink-two-gpu-racing.md) — no-NVLink reality and the racing pivot
- [ADR-0005](../../adr/0005-postgres-tenant-no-neo4j.md) — Graphiti dropped; Postgres-only Phase 1–2
- [`docs/plan.md`](../../plan.md) — the canonical implementation plan
