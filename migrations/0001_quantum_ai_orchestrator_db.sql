-- 0001_quantum_ai_orchestrator_db.sql
-- Creates the quantum_ai_orchestrator database (idempotent) and the common.* tables.
-- Run this against the supabase-db Postgres via the supavisor pooler.
--
-- Connection: psql -h localhost -p 5432 -U postgres -d postgres -f 0001_quantum_ai_orchestrator_db.sql
--
-- Note: CREATE DATABASE cannot run inside a transaction. We use a DO block with
-- dynamic SQL so that re-runs don't fail when the database already exists.

\set ON_ERROR_STOP on

-- 1. Create the database if it doesn't exist.
SELECT 'CREATE DATABASE quantum_ai_orchestrator'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'quantum_ai_orchestrator')
\gexec

-- 2. Switch to the new database for the rest of the migration.
\connect quantum_ai_orchestrator

-- 3. The 'common' schema holds tables shared across all skills:
--    runs, problem_graphs, dispatches, outcomes, lessons.
CREATE SCHEMA IF NOT EXISTS common;

-- Enable pgcrypto for gen_random_uuid() (Supabase usually already has it).
CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;

-- runs: one row per natural-language ask processed by the orchestrator.
CREATE TABLE IF NOT EXISTS common.runs (
    run_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ask_text      TEXT NOT NULL,
    skill         TEXT NOT NULL,
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ,
    status        TEXT NOT NULL CHECK (status IN ('running','succeeded','failed'))
);
CREATE INDEX IF NOT EXISTS runs_started_at_idx ON common.runs (started_at DESC);
CREATE INDEX IF NOT EXISTS runs_skill_status_idx ON common.runs (skill, status);

-- problem_graphs: the DAG produced by the Decomposer, one row per node.
CREATE TABLE IF NOT EXISTS common.problem_graphs (
    graph_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id        UUID NOT NULL REFERENCES common.runs(run_id) ON DELETE CASCADE,
    problem_id    TEXT NOT NULL,
    parent_id     TEXT,
    problem_class TEXT NOT NULL CHECK (problem_class IN
                    ('qec_syndrome','qubo_assignment','qubo_routing','qubo_portfolio')),
    fingerprint   BYTEA NOT NULL,
    params        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS problem_graphs_run_id_idx ON common.problem_graphs (run_id);
CREATE INDEX IF NOT EXISTS problem_graphs_problem_id_idx ON common.problem_graphs (problem_id);
CREATE INDEX IF NOT EXISTS problem_graphs_fingerprint_idx ON common.problem_graphs (fingerprint);
CREATE INDEX IF NOT EXISTS problem_graphs_class_idx ON common.problem_graphs (problem_class);

-- dispatches: one row per (problem leaf, backend) pair we kicked off.
CREATE TABLE IF NOT EXISTS common.dispatches (
    dispatch_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    graph_id       UUID NOT NULL REFERENCES common.problem_graphs(graph_id) ON DELETE CASCADE,
    problem_id     TEXT NOT NULL,
    backend_name   TEXT NOT NULL,
    gpu_lane       INT,
    dispatched_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS dispatches_graph_id_idx ON common.dispatches (graph_id);
CREATE INDEX IF NOT EXISTS dispatches_backend_idx ON common.dispatches (backend_name);

-- outcomes: one row per finished backend invocation.
CREATE TABLE IF NOT EXISTS common.outcomes (
    outcome_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dispatch_id    UUID NOT NULL REFERENCES common.dispatches(dispatch_id) ON DELETE CASCADE,
    quality        NUMERIC,
    wall_time_ms   INT,
    metric_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    finished_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS outcomes_dispatch_id_idx ON common.outcomes (dispatch_id);
CREATE INDEX IF NOT EXISTS outcomes_finished_at_idx ON common.outcomes (finished_at DESC);

-- lessons: bi-temporal preference table the Strategist updates between asks.
-- valid_from / valid_to lets us answer "as of time T, why did we pick backend B for class C?"
CREATE TABLE IF NOT EXISTS common.lessons (
    lesson_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    problem_class     TEXT NOT NULL CHECK (problem_class IN
                        ('qec_syndrome','qubo_assignment','qubo_routing','qubo_portfolio')),
    size_bucket       TEXT NOT NULL,
    preferred_backend TEXT NOT NULL,
    confidence        NUMERIC NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    rationale         TEXT,
    valid_from        TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_to          TIMESTAMPTZ,
    CHECK (valid_to IS NULL OR valid_to > valid_from)
);
CREATE INDEX IF NOT EXISTS lessons_class_size_validity_idx
    ON common.lessons (problem_class, size_bucket, valid_from, valid_to);

COMMENT ON TABLE common.lessons IS
    'Bi-temporal: a row is currently valid when valid_to IS NULL or valid_to > now(). When the Strategist updates a preference, set valid_to on the old row and INSERT a new one; never UPDATE in place.';
