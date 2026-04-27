"""Insert/update operations for `common.runs`."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from .pool import execute, fetch_one, get_pool

logger = logging.getLogger(__name__)


def insert_run_start(
    run_id: UUID,
    ask_text: str,
    skill: str,
    started_at: datetime,
    status: str = "running",
) -> None:
    execute(
        """
        INSERT INTO common.runs (run_id, ask_text, skill, started_at, status)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (str(run_id), ask_text, skill, started_at, status),
    )
    logger.info("runs: inserted %s (status=%s)", run_id, status)


def update_run_finish(
    run_id: UUID,
    status: str,
    finished_at: datetime,
) -> None:
    execute(
        """
        UPDATE common.runs
           SET status = %s, finished_at = %s
         WHERE run_id = %s
        """,
        (status, finished_at, str(run_id)),
    )
    logger.info("runs: marked %s -> %s", run_id, status)


def update_run_skill(run_id: UUID, skill: str) -> None:
    """Update the run's skill once decompose names it."""
    execute(
        "UPDATE common.runs SET skill = %s WHERE run_id = %s",
        (skill, str(run_id)),
    )


def insert_problem_graph_row(
    graph_id: UUID,
    run_id: UUID,
    problem_id: str,
    parent_id: str | None,
    problem_class: str,
    fingerprint: bytes,
    params: dict[str, Any],
    created_at: datetime,
) -> None:
    execute(
        """
        INSERT INTO common.problem_graphs (
            graph_id, run_id, problem_id, parent_id, problem_class,
            fingerprint, params, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            str(graph_id),
            str(run_id),
            problem_id,
            parent_id,
            problem_class,
            fingerprint,
            Jsonb(params),
            created_at,
        ),
    )


def fetch_run(run_id: UUID) -> dict[str, Any] | None:
    return fetch_one(
        "SELECT * FROM common.runs WHERE run_id = %s",
        (str(run_id),),
    )


def fetch_recent_runs(limit: int = 10) -> list[dict[str, Any]]:
    """Return the N most recent runs, newest first."""
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM common.runs ORDER BY started_at DESC LIMIT %s",
                (limit,),
            )
            return cur.fetchall()
