"""Insert operations for `common.dispatches`.

Each row records a single (problem, backend) racing pair — there are
N rows per problem when we race N backends. The winner is identified
post-hoc by joining outcomes and picking max quality, not by tagging
a column on the dispatch row.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from .pool import execute

logger = logging.getLogger(__name__)


def insert_dispatch(
    dispatch_id: UUID,
    graph_id: UUID,
    problem_id: str,
    backend_name: str,
    gpu_lane: int | None,
    dispatched_at: datetime,
) -> None:
    execute(
        """
        INSERT INTO common.dispatches (
            dispatch_id, graph_id, problem_id, backend_name, gpu_lane, dispatched_at
        ) VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            str(dispatch_id),
            str(graph_id),
            problem_id,
            backend_name,
            gpu_lane,
            dispatched_at,
        ),
    )
    logger.debug(
        "dispatches: %s -> %s (backend=%s, gpu_lane=%s)",
        dispatch_id, problem_id, backend_name, gpu_lane,
    )
