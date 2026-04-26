-- 0005_portfolio_schema.sql
-- Per-skill schema for portfolio.
-- Run against quantum_ai_orchestrator database (after 0001).
-- Idempotent.

\set ON_ERROR_STOP on
\connect quantum_ai_orchestrator

CREATE SCHEMA IF NOT EXISTS portfolio;

-- Skill-specific tables get added here as Phase 1+ work lands.
-- Day-1 the schema is empty; we are reserving the namespace.
COMMENT ON SCHEMA portfolio IS 'Skill-specific tables for the portfolio skill. Common provenance lives in common.*';
