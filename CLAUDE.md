# CLAUDE.md — quantum-ai-orchestrator

This file is auto-loaded by Claude Code when you open this directory. Read it. Then read [`docs/plan.md`](docs/plan.md). Then start work.

## What this project is

An **AI-orchestrated control plane for hybrid quantum-classical workloads**. Takes a natural-language ask, decomposes it via a local LLM into a problem graph, dispatches each leaf in parallel across a portfolio of GPU-backed solvers (classical, quantum-inspired annealing, GPU statevector simulation, AI quantum-error-correction decoders), races them, picks the winner, reassembles the answer, and records every decision in an auditable Postgres provenance log.

Substrate today is GPUs. The pipeline is designed so QPU backends slot in unchanged when they arrive.

## Where the canonical reference lives

[`docs/plan.md`](docs/plan.md) — the canonical implementation plan. ~533 lines. Read it before doing anything in this repo.

## Hardware reality

This project runs on **kaiju** (Dell Precision 7960):

- 2× NVIDIA RTX 6000 Ada Generation, 48 GB each, compute cap 8.9, FP8 native
- **No NVLink** — architectural; the RTX 6000 Ada family doesn't have it. PCIe-only across NUMA. We pivoted to *each GPU runs a different backend in parallel*, which the dashboard literalizes in the Backend Bake-off panel. See ADR-0002.
- Intel Xeon w9-3495X, 56C/112T, AMX + AVX-512 (Sapphire Rapids — exceptional classical-baseline perf)
- 502 GiB RAM, 2.7 TB free on `/data`
- Ubuntu 22.04.5, NVIDIA driver 535.288.01

Full recon results: [`docs/host-setup.md`](docs/host-setup.md).

## What's already on kaiju that we use as a tenant

- **Supabase** at `/data/docker/supabase/` — full self-hosted stack. We are a Postgres tenant: database `quantum_ai_orchestrator`, per-skill schemas. Connection via supavisor pooler at `localhost:5432`. See ADR-0005.
- **Ollama** at `localhost:11434` — `gemma4:31b-it-q8_0` already pulled; this is our default Decomposer LLM. See ADR-0004.
- **Litellm gateway** at `localhost:4000` — available if we want a unified LLM client.

We do **not** stand up our own Postgres or Neo4j. The host Neo4j on `:7474/:7687` is a generic instance — not ours; do not write to it.

## Architectural shape (locked)

The orchestrator is a **pipeline**, not a retry loop. Six modules under `orchestrator/pipeline/`:

```
NL ask
  └─ decomposer.py     (Gemma 4 → problem-graph DAG)
       └─ formulator.py     (leaf → backend-ready input, dispatches by problem_class)
            └─ dispatcher.py     (picks 1+ backends from registry + Postgres preference table)
                 ├─ Backend A    ─┐
                 ├─ Backend B    ─┤── evaluator.py    (scores quality / wall_time / energy_or_LER)
                 └─ Backend C    ─┘
                      ├─ reassembler.py    (walks DAG bottom-up)
                      └─ strategist.py     (between asks: updates Postgres preferences)
                           │
                           └─ All decisions appended to Postgres provenance tables
```

Skills live under `skills/<name>/` and provide three things: a `formulator.py`, an `evaluator.py`, and a UI panel. No five-Protocol contract, no Checkpoint, no FailureMode enum. See [`docs/plan.md`](docs/plan.md) §5 for the full pipeline spec.

## Other locked decisions

- **Decomposer LLM**: `gemma4:31b-it-q8_0` (Apache 2.0 weights; validated for tool use + JSON output). Phase-0 benches alternates against a fixed prompt suite — ADR-0004 will lock or break the tie.
- **Containerized CUDA-Q.** Use `nvcr.io/nvidia/cuda-quantum:0.9.x` with driver 535 forward-compat — don't touch the host driver. See ADR-0003.
- **Two-GPU racing.** Each backend that needs a GPU gets its own lane (GPU0 or GPU1). The dispatcher assigns lanes; the dashboard shows literal parallel races. See ADR-0002.
- **Visualization stack is first-class.** Stim (Apache 2.0), Crumble, PyMatching, D-Wave problem-inspector, QuTiP, react-three-fiber + drei, deck.gl, Plotly.js. Each panel maps to specific libraries; see plan §8. Phase-0 includes 5 viz smoke renders. ADR-0009 documents.

## Phase 0 task list (what's pending)

This Claude Code session ran the SCAFFOLD half of Phase 0:
- Repo created on GitHub, public
- LICENSE, README, this file, plan, journey 00, ADR template, STYLE.md, ADRs 0001/0002/0005 committed
- `quantum_ai_orchestrator` Postgres database created with 5 schemas migrated
- `.env` populated with credentials extracted from supabase

You're picking up the INSTALL half:
1. `uv venv --python 3.11 && uv pip install -e .[dev]`
2. Pull `nvcr.io/nvidia/cuda-quantum:0.9.x` container; verify it runs with driver 535
3. Run `tools/bootstrap_ising.sh` to pull NVIDIA Ising Decoding weights to `/data/models/nvidia-ising/`
4. Run `tools/bench_decomposers.sh` to bench candidate Decomposer LLMs on Ollama
5. Run all 11 smoke tests under `tests/smoke/` (6 numerical + 5 visualization — see plan §3 and §8)
6. Write the ADRs that land based on actual environment results (0003 CUDA-Q container, 0004 Decomposer choice, 0006 PyMatching+Stim integration, 0008 Crumble iframe-vs-port, 0009 visualization stack, 0010 Python version fallback if needed)
7. Commit smoke logs to `runs/smoke/`

Then start Phase 1: `qec_decode` and `mission_assignment` skills end-to-end.

## Where the credentials are

`/data/code/quantum-ai-orchestrator/.env` (gitignored). It contains *only* the Postgres credentials we need:

```
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<extracted from /data/docker/supabase/.env>
POSTGRES_DB=quantum_ai_orchestrator
```

Do not commit it. Do not copy other supabase secrets in. ADR-0001 documents the credential-hygiene rule.

## The journey discipline

Read [`docs/journal/STYLE.md`](docs/journal/STYLE.md) before writing any journey entry. Voice target: *Dan Luu's observational restraint + Andy Weir's predicament-first immediacy + Matt Levine's permission to call out absurdity.*

- Predicament-first openings (don't start with "in this entry we will...")
- Specific over abstract (numbers, file paths, function names)
- Honest about failures and surprises
- Pull-quotes via mkdocs-material `!!! quote ""` admonitions, sparingly
- No emojis ever
- Prediction entries land *before* outcome entries — non-negotiable

[`docs/journal/journey/00-origin.md`](docs/journal/journey/00-origin.md) is the seed. Pattern your entries on it.

## What "done" looks like

- **Phase 0 done** when `make smoke` runs all 11 gates green; `docs/host-setup.md` and ADRs 0001–0009 exist; the public GitHub repo is live with `LICENSE`, `README.md`, `CLAUDE.md`, `docs/plan.md`, journey entry 00; `quantum_ai_orchestrator` database exists in supabase-db with all five schemas migrated.
- **Phase 1 done** when `bin/qao run "decode a distance-5 surface code at p=1e-3"` produces a corrected logical state with three decoder lines on the LER chart, a populated dashboard, a Run row in Postgres `common.runs`, dispatch + outcome rows, no manual intervention; AND `bin/qao run "assign 12 assets across 8 tasks with capacity constraint K=3"` produces a parallel-backend race, an assignment, and a fresh row in `common.lessons`.

If you can't tell whether you're done, you aren't. Read the verification section at the end of [`docs/plan.md`](docs/plan.md).

## Tone: an honest engineering exploration, not a product

This is a public, customer-shareable exploration of AI use in quantum — built for technical presales engineers, Dell partners, and customers who want to go deep into how it works. It is not a product, and nothing here is going through procurement. The README, the journey, every ADR — all should read as *honest engineering for engineers*. That means:

- No cheerleading. No "revolutionary" or "game-changing."
- When something doesn't work, name it. Failures are part of the value of the journal.
- When a decision is a trade-off, name both sides.
- When we don't have a real QPU, say so explicitly in the dashboard footer.

The audience is technical, curious, and skeptical. Write for someone who will read your code and your reasoning side-by-side.
