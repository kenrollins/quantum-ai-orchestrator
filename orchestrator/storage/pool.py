"""Postgres connection pool against the supabase-hosted database.

Reads connection settings from env (POSTGRES_HOST etc.). The CLI loads
`.env` at import time so subcommands inherit these without manual sourcing.

We use a synchronous `psycopg_pool.ConnectionPool` rather than the async
variant: writes are tiny relative to the pipeline (compared to GPU forward
passes, container subprocesses, LLM calls), so the cost of running them
in `asyncio.to_thread` is negligible and we avoid pool lifecycle headaches
across the async boundary.
"""

from __future__ import annotations

import logging
import os
from threading import Lock
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)

_POOL: ConnectionPool | None = None
_POOL_LOCK = Lock()


def _conninfo_from_env() -> str:
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "quantum_ai_orchestrator")
    user = os.environ.get("POSTGRES_USER", "postgres")
    pwd = os.environ.get("POSTGRES_PASSWORD")
    if not pwd:
        raise RuntimeError(
            "POSTGRES_PASSWORD not set. Source .env or set the env var."
        )
    return f"host={host} port={port} dbname={db} user={user} password={pwd}"


def get_pool() -> ConnectionPool:
    """Return the process-wide pool, creating it lazily on first use."""
    global _POOL
    if _POOL is not None:
        return _POOL
    with _POOL_LOCK:
        if _POOL is not None:
            return _POOL
        _POOL = ConnectionPool(
            conninfo=_conninfo_from_env(),
            min_size=1,
            max_size=8,
            kwargs={"row_factory": dict_row, "autocommit": False},
            open=True,
        )
        logger.info("Postgres pool opened (min=1, max=8)")
        return _POOL


def close_pool() -> None:
    """Close the pool (useful in tests / clean shutdown)."""
    global _POOL
    with _POOL_LOCK:
        if _POOL is not None:
            _POOL.close()
            _POOL = None


def execute(sql: str, params: tuple | dict[str, Any] | None = None) -> None:
    """Run an INSERT/UPDATE/DELETE in its own committed transaction."""
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()


def fetch_one(sql: str, params: tuple | dict[str, Any] | None = None) -> dict[str, Any] | None:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()


def fetch_all(sql: str, params: tuple | dict[str, Any] | None = None) -> list[dict[str, Any]]:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
