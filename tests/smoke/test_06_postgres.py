"""Phase-0 numerical gate 6: psycopg.connect() to `quantum_ai_orchestrator`
via the supavisor pooler succeeds, all five schemas are present, and the
common.* tables are queryable.

Credentials read from /data/code/quantum-ai-orchestrator/.env (gitignored).
"""

from __future__ import annotations

import time
from pathlib import Path

import psycopg
import pytest

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
EXPECTED_SCHEMAS = {"common", "qec_decode", "mission_assignment", "routing", "portfolio"}
EXPECTED_COMMON_TABLES = {"runs", "problem_graphs", "dispatches", "outcomes", "lessons"}


def _load_env() -> dict[str, str]:
    if not ENV_PATH.exists():
        pytest.skip(f"{ENV_PATH} not present")
    env = {}
    for line in ENV_PATH.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()
    return env


@pytest.mark.numerical
def test_postgres_tenancy_smoke(write_artifact):
    env = _load_env()
    for required in ("POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_USER", "POSTGRES_PASSWORD"):
        if required not in env:
            pytest.skip(f"{required} missing from .env")

    dsn = (
        f"host={env['POSTGRES_HOST']} port={env['POSTGRES_PORT']} "
        f"user={env['POSTGRES_USER']} password={env['POSTGRES_PASSWORD']} "
        f"dbname={env.get('POSTGRES_DB', 'quantum_ai_orchestrator')}"
    )

    t0 = time.perf_counter()
    with psycopg.connect(dsn, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute("select current_database(), current_user, version()")
            db, user, version = cur.fetchone()
            cur.execute(
                "select schema_name from information_schema.schemata "
                "where schema_name = any(%s)",
                (list(EXPECTED_SCHEMAS),),
            )
            schemas = {r[0] for r in cur.fetchall()}
            cur.execute(
                "select table_name from information_schema.tables where table_schema='common'"
            )
            tables = {r[0] for r in cur.fetchall()}
    dt_s = time.perf_counter() - t0

    payload = {
        "wall_seconds": dt_s,
        "database": db,
        "user": user,
        "server_version": version.split(" on ")[0],
        "schemas_found": sorted(schemas),
        "common_tables_found": sorted(tables),
    }
    write_artifact("06_postgres.json", payload)

    assert db == "quantum_ai_orchestrator", f"connected to {db!r}"
    assert EXPECTED_SCHEMAS <= schemas, f"missing schemas: {EXPECTED_SCHEMAS - schemas}"
    assert EXPECTED_COMMON_TABLES <= tables, (
        f"missing common.* tables: {EXPECTED_COMMON_TABLES - tables}"
    )
