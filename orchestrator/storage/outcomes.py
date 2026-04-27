"""Insert operations for `common.outcomes`.

One row per dispatch, recording how that backend's solution scored.
The metric_payload jsonb captures backend-specific fields (LER for QEC,
objective + feasibility for assignment, etc.). The grader stores raw
floats/ints/strs so jsonb-friendly; numpy arrays etc. need sanitizing
upstream.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from .pool import execute

logger = logging.getLogger(__name__)


def _json_safe(obj: Any) -> Any:
    """Recursive sanitize for Jsonb storage. Drops or stringifies non-trivial values."""
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    # numpy scalar -> python scalar (avoid hard import on numpy here)
    if hasattr(obj, "item") and callable(getattr(obj, "item", None)):
        try:
            return obj.item()
        except Exception:
            pass
    if hasattr(obj, "tolist") and callable(getattr(obj, "tolist", None)):
        try:
            return _json_safe(obj.tolist())
        except Exception:
            pass
    return str(obj)


def insert_outcome(
    outcome_id: UUID,
    dispatch_id: UUID,
    quality: float | None,
    wall_time_ms: int | None,
    metric_payload: dict[str, Any],
    finished_at: datetime,
) -> None:
    execute(
        """
        INSERT INTO common.outcomes (
            outcome_id, dispatch_id, quality, wall_time_ms, metric_payload, finished_at
        ) VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            str(outcome_id),
            str(dispatch_id),
            quality,
            wall_time_ms,
            Jsonb(_json_safe(metric_payload)),
            finished_at,
        ),
    )
    logger.debug(
        "outcomes: %s -> dispatch=%s quality=%s wall=%sms",
        outcome_id, dispatch_id, quality, wall_time_ms,
    )
