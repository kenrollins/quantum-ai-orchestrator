"""Strategist: Learn backend preferences from outcomes.

Phase 2 module. For Phase 1, this is a stub that does nothing.

When implemented, the Strategist will:
1. Analyze outcomes from multiple runs
2. Identify which backends perform best for each (problem_class, size_bucket)
3. Update the bi-temporal preference table in Postgres
4. The Dispatcher reads these preferences to prioritize backends
"""

from __future__ import annotations

import logging
from typing import Any

from .types import Lesson, Outcome, ProblemClass

logger = logging.getLogger(__name__)


async def record_outcome(outcome: Outcome) -> None:
    """Record an outcome for future learning.

    Phase 2: Will insert into Postgres outcomes table.
    Phase 1: No-op stub.

    Args:
        outcome: The outcome to record.
    """
    logger.debug(
        "Strategist stub: would record outcome for %s (backend=%s, quality=%.4f)",
        outcome.problem.problem_id,
        outcome.backend_choice.backend.name,
        outcome.grade.quality,
    )
    # TODO: Insert into Postgres common.outcomes


async def update_preferences(
    problem_class: ProblemClass,
    size_bucket: str,
    min_samples: int = 10,
) -> Lesson | None:
    """Analyze outcomes and update preferences for a problem class/bucket.

    Phase 2: Will query outcomes, compute statistics, and update lessons.
    Phase 1: No-op stub that returns None.

    Args:
        problem_class: The problem class to analyze.
        size_bucket: The size bucket to analyze.
        min_samples: Minimum samples required before updating.

    Returns:
        The new Lesson if one was created, None otherwise.
    """
    _ = min_samples  # Will be used in Phase 2
    logger.debug(
        "Strategist stub: would update preferences for %s/%s",
        problem_class.value,
        size_bucket,
    )
    # TODO: Implement preference learning:
    # 1. Query recent outcomes for this (problem_class, size_bucket)
    # 2. Group by backend, compute avg quality and success rate
    # 3. If one backend is clearly better, create a Lesson
    # 4. Insert Lesson into Postgres with bi-temporal timestamps
    return None


async def get_preference_stats(
    problem_class: ProblemClass,
    size_bucket: str,
) -> dict[str, Any]:
    """Get statistics about backend performance for a problem class/bucket.

    Phase 2: Will query and aggregate outcome data.
    Phase 1: Returns empty stats.

    Args:
        problem_class: The problem class to query.
        size_bucket: The size bucket to query.

    Returns:
        Dictionary with performance statistics per backend.
    """
    logger.debug(
        "Strategist stub: would get stats for %s/%s",
        problem_class.value,
        size_bucket,
    )
    return {
        "problem_class": problem_class.value,
        "size_bucket": size_bucket,
        "backends": {},
        "sample_count": 0,
        "message": "Strategist not yet implemented (Phase 2)",
    }


async def expire_stale_lessons(max_age_days: int = 30) -> int:
    """Expire lessons that haven't been validated recently.

    Phase 2: Will update valid_to on stale Lessons.
    Phase 1: No-op stub.

    Args:
        max_age_days: Lessons older than this without validation are expired.

    Returns:
        Count of expired lessons.
    """
    logger.debug(
        "Strategist stub: would expire lessons older than %d days",
        max_age_days,
    )
    return 0


# Synchronous wrappers for CLI/testing
def record_outcome_sync(outcome: Outcome) -> None:
    """Synchronous wrapper for record_outcome()."""
    import asyncio
    asyncio.run(record_outcome(outcome))


def update_preferences_sync(
    problem_class: ProblemClass,
    size_bucket: str,
    min_samples: int = 10,
) -> Lesson | None:
    """Synchronous wrapper for update_preferences()."""
    import asyncio
    return asyncio.run(update_preferences(problem_class, size_bucket, min_samples))
