# ADR-0005: Postgres-tenant of supabase; no Neo4j in Phase 1–2

- **Status:** Accepted
- **Date:** 2026-04-26
- **Deciders:** Ken Rollins

## Context

Gemma-forge uses Graphiti (a bi-temporal knowledge-graph framework) on Neo4j as its agent-memory backend, with Postgres for episodic state and a dream pass that consolidates lessons between runs. It works because gemma-forge does agentic memory at scale: vector retrieval over reflections, fulltext indexes for lesson assembly, audit traces over arbitrary subgraphs.

This project's load profile is different. Per ask, we record:

- one row in `runs`
- a small DAG (1–10 rows) in `problem_graphs`
- a handful of rows (1–10) in `dispatches` (one per backend invoked)
- one row per backend in `outcomes`
- zero or one row in `lessons` (only when the Strategist runs and finds a meaningfully-novel preference)

That is tens of records per ask, not thousands. We do not need vector retrieval over outcomes. We do not need fulltext indexes over reflections. We need bi-temporal queries (*"what was the preferred backend for class C as of last Tuesday?"*) and recursive ancestry traversals (*"trace this leaf back to the original ask"*).

Plain Postgres handles both. `valid_from / valid_to` columns + indexes give bi-temporal querying. Recursive CTEs traverse problem-graph ancestry. The audit story reads in SQL — which any technical reader and standard tools (Grafana, Metabase, psql) speak natively.

The workstation already runs a full Supabase stack at `/data/docker/supabase/`. We become a tenant: one new database (`quantum_ai_orchestrator`), per-skill schemas inside it.

## Decision

**Postgres-only for Phase 1 and Phase 2.** No Graphiti, no Neo4j, no separate graph database.

- Database: `quantum_ai_orchestrator` (created by migration `0001`)
- Schemas: `common`, `qec_decode`, `mission_assignment`, `routing`, `portfolio` (all created day-1; Phase 2/3 schemas empty until those skills land)
- Connection: via the supavisor pooler at `localhost:5432` (or `:6543` for transaction-mode pool)
- Bi-temporal: `valid_from / valid_to` columns on `common.lessons`
- Audit traversal: recursive CTE over `common.problem_graphs`
- Credentials: project `.env` carries only the Postgres values, extracted from `/data/docker/supabase/.env` (which holds many other unrelated secrets — Langfuse, JWT, dashboard password — that we never copy)

**Phase 3 may add Neo4j as a visualization layer** (graph render in the dashboard) following the dell-vendor convention: a project-specific `quantum-ai-orchestrator-neo4j` container on alternate ports under `/data/docker/quantum-ai-orchestrator/`. Not committed Phase 1.

## Alternatives considered

- **Carry over Graphiti + Neo4j unchanged.** Working pattern in gemma-forge; lowest-friction inheritance. But the load profile doesn't justify the operational weight, and the audit story tells better in SQL than Cypher for this audience. Rejected.
- **Stand up our own Postgres container.** Cleanest isolation; no shared-host dependencies. But adds infra to manage, and the supabase-db tenant pattern is well-precedented on this host (the supabase pooler isolates by database). Rejected — tenancy is the right move.
- **Use Apache AGE (Postgres graph extension).** Lets us write Cypher against Postgres if we want graph semantics. Real option for Phase 3 if the dashboard graph viz benefits and we want to avoid standing up Neo4j. Documented as a Phase 3 alternative in the plan; not Phase 1.
- **DuckDB or SQLite local file.** Federal-evaluator-friendly because there's no network database to audit. But loses the supabase tenancy benefits (managed backups, connection pooling, observability). Rejected for Phase 1; possibly useful for offline replay.

## Consequences

### Positive

- Zero new infra on the workstation in Phase 1 — just migrations against an existing service.
- Audit queries are plain SQL — readable by any technical reviewer; tool-friendly (Grafana/Metabase/psql).
- Bi-temporal pattern is well-understood; many engineers can read and extend `valid_from / valid_to` schemas without learning Graphiti.
- Per-skill schemas isolate cleanly, so adding skills 3 and 4 doesn't interact with schema 1 and 2.

### Negative / accepted trade-offs

- We share a Postgres instance with other projects on the workstation. Tenancy isolation enforced by always operating scoped to the `quantum_ai_orchestrator` database; migrations are idempotent (`CREATE SCHEMA IF NOT EXISTS …`).
- If the dashboard genuinely benefits from a graph visualization later, we'll need to add Neo4j or AGE in Phase 3. The cost of adding it then is small (the data lives in Postgres; Neo4j becomes a derived view).
- `/data/docker/supabase/.env` contains credentials we don't need. The bootstrap script reads only the Postgres-related keys; the rest stay where they are.

## References

- Plan: [`../plan.md`](../plan.md), §9 (Storage and Provenance — Postgres-Only)
- Host setup: [`../host-setup.md`](../host-setup.md)
- Gemma-forge ADR-0016 (the inheritance we declined): `/data/code/gemma-forge/docs/adr/0016-graphiti-neo4j-postgres-memory-stack.md`
- Apache AGE (deferred Phase 3 alternative): https://age.apache.org
