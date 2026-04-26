# Host setup — kaiju

Recon results from 2026-04-25, captured during planning. Re-verify any claim before relying on it; this is a snapshot.

## Hardware

| Item | Reality |
|---|---|
| Chassis | Dell Precision 7960 |
| GPUs | 2× NVIDIA RTX 6000 Ada Generation, 48 GB each, compute cap 8.9, FP8 native |
| NVLink | **Architecturally absent** — RTX 6000 Ada family doesn't include NVLink. PCIe-only across NUMA. No bridge can be added. See ADR-0002. |
| CPU | Intel Xeon w9-3495X, 56C/112T, AMX + AVX-512 (Sapphire Rapids) |
| RAM | 502 GiB |
| Storage | `/data` 3.7 TB (RAID md0), 2.7 TB free |
| OS | Ubuntu 22.04.5 (jammy) |
| NVIDIA driver | 535.288.01 (CUDA 12.2 era — see containerized-CUDA-Q decision in ADR-0003) |
| `nvcc` | not installed system-wide; we use the CUDA-Q container |

## Topology probe

```
$ nvidia-smi topo -m
        GPU0    GPU1    CPU Affinity    NUMA Affinity   GPU NUMA ID
GPU0     X      SYS     0-111           0               N/A
GPU1    SYS     X       0-111           0               N/A
```

`SYS` = traverses PCIe + NUMA interconnect. No `NV#` peer-to-peer link. Confirms NVLink absence.

```
$ nvidia-smi nvlink --status        # empty output
$ nvidia-smi nvlink --capabilities  # empty output
```

GPUs at PCIe addresses `0000:ac:00.0` (GPU0) and `0000:ca:00.0` (GPU1), connected only via Intel PCIe bridges.

## Already-running services on kaiju

The host is busy. We are tenants of these existing services:

- **Supabase** at `/data/docker/supabase/` — full stack. We use the Postgres at `localhost:5432` (via supavisor pooler) for `quantum_ai_orchestrator` database.
- **Ollama** at `localhost:11434`. Catalog includes `gemma4:31b-it-q8_0` (33 GB, our default Decomposer), `gemma4:26b` MoE, `qwen3-coder-next` (51 GB), `nemotron-3-nano:30b`, `llama3.3:70b-instruct-q8_0`, plus embeddings (`bge-m3`, `nomic-embed-text`).
- **Litellm gateway** at `localhost:4000` — unified LLM client; available if useful.
- **Neo4j** at `localhost:7474/7687` — generic instance, NOT ours. `dell-vendor-neo4j` at `:7747/:7688` is the dell-vendor-intel project's. We do not stand up our own Neo4j in Phase 1.
- **Qdrant** at `:6333/:6334`, **Redis** at `:6379`, **Traefik** at `:80/:8080`, **n8n** at `:5678`, **Letta** at `:8083/:8283`, **Infinity embeddings** at `:7997` — available as clients if needed.

## Toolchain on host

- `uv` 0.7.19 (already present)
- Python 3.10.12 system; we use `uv venv --python 3.11` for project venv
- Docker 29.4.0
- `git` 2.34.1
- `gh` (GitHub CLI) — verify version in Phase 0
- `psql` available via supabase-db image; project uses `psycopg[binary,pool] 3.2.x` from venv

## Naming-convention precedent on this host

`/data/code/dell-vendor-intel/` exists and uses the `dell-vendor-*` naming convention; corresponding services run as `dell-vendor-<service>` containers on alternate ports. Our project intentionally avoids the `dell-` prefix in the public repo name (per ADR-0001) — README does the Dell positioning.

## What this means for the build

- Containerized CUDA-Q lets us avoid touching the host driver.
- No NVLink → we lean into two-GPU parallel racing rather than memory pooling.
- Postgres-as-tenant means no new container infra in Phase 1 — just migrations against `supabase-db`.
- Sapphire Rapids AMX makes OR-Tools and PyMatching CPU baselines exceptionally fast — important for the bake-off fairness story.
