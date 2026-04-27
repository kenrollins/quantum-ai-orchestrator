"""Postgres provenance storage for the orchestrator.

Schema lives in the `common` namespace of the `quantum_ai_orchestrator`
database (migrated in Phase 0). Five tables:

- `runs`           one row per pipeline invocation
- `problem_graphs` one row per leaf problem within a run
- `dispatches`     one row per (problem, backend) racing pair
- `outcomes`       one row per dispatch with score + raw metrics
- `lessons`        learned preferences, bi-temporal (Phase 2)

`record_run` is the single entry point the runner calls at the end of
each pipeline execution — it writes the run, graph, dispatches, and
outcomes in dependency order.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from orchestrator.pipeline.types import Run

from . import dispatches as _dispatches
from . import outcomes as _outcomes
from . import runs as _runs
from .pool import close_pool, execute, fetch_all, fetch_one, get_pool

logger = logging.getLogger(__name__)

__all__ = [
    "close_pool",
    "execute",
    "fetch_all",
    "fetch_one",
    "get_pool",
    "record_run",
    "record_run_start",
]


def record_run_start(run: Run) -> None:
    """Insert the initial `runs` row at pipeline start.

    Skill is "unknown" until the decomposer fires; we update it later
    via `_runs.update_run_skill`. status is "running".
    """
    started = run.started_at if run.started_at else datetime.now(timezone.utc)
    _runs.insert_run_start(
        run_id=run.run_id,
        ask_text=run.ask_text,
        skill=run.skill or "unknown",
        started_at=started,
        status=run.status.value if hasattr(run.status, "value") else str(run.status),
    )


def record_run(run: Run) -> None:
    """Persist a completed Run, including its graph, dispatches, and outcomes.

    Idempotency: callers should call this once at the end of a pipeline
    execution. We do not retry on partial failure — a runtime error
    here gets logged and re-raised; the run is captured in process
    state regardless.

    Order matters because of FKs:
      runs (already inserted by record_run_start) -> update finish
        -> problem_graphs -> dispatches -> outcomes
    """
    finished = run.finished_at if run.finished_at else datetime.now(timezone.utc)

    # 1. Update the run row's skill (decomposer set it) and finish status.
    if run.skill and run.skill != "unknown":
        _runs.update_run_skill(run.run_id, run.skill)
    _runs.update_run_finish(
        run_id=run.run_id,
        status=run.status.value if hasattr(run.status, "value") else str(run.status),
        finished_at=finished,
    )

    if run.problem_graph is None:
        # Decomposition failed — nothing further to record.
        logger.info("record_run: no problem_graph on run %s; stopping after run row", run.run_id)
        return

    # 2. Write a problem_graphs row per problem. Re-use one graph_id per
    #    problem so dispatches can reference a stable graph_id.
    problem_to_graph_id: dict[str, UUID] = {}
    created_at = run.started_at or datetime.now(timezone.utc)
    for problem in run.problem_graph.problems:
        graph_id = uuid4()
        problem_to_graph_id[problem.problem_id] = graph_id
        _runs.insert_problem_graph_row(
            graph_id=graph_id,
            run_id=run.run_id,
            problem_id=problem.problem_id,
            parent_id=problem.parent_id,
            problem_class=problem.problem_class.value,
            fingerprint=problem.fingerprint,
            params=problem.params,
            created_at=created_at,
        )

    # 3. Dispatches + outcomes for every race participant (winners and losers).
    #    `run.race_history` carries all; `run.outcomes` only the winners.
    #    We persist race_history to keep the dashboard's bake-off panel honest.
    rows_to_record = run.race_history if run.race_history else run.outcomes
    for outcome in rows_to_record:
        graph_id = problem_to_graph_id.get(outcome.problem.problem_id)
        if graph_id is None:
            logger.warning(
                "record_run: outcome problem_id=%s missing from graph; skipping",
                outcome.problem.problem_id,
            )
            continue
        _dispatches.insert_dispatch(
            dispatch_id=outcome.dispatch_id,
            graph_id=graph_id,
            problem_id=outcome.problem.problem_id,
            backend_name=outcome.backend_choice.backend.name,
            gpu_lane=outcome.backend_choice.gpu_lane,
            dispatched_at=outcome.dispatched_at,
        )
        _outcomes.insert_outcome(
            outcome_id=uuid4(),
            dispatch_id=outcome.dispatch_id,
            quality=float(outcome.grade.quality) if outcome.grade.quality is not None else None,
            wall_time_ms=outcome.solution.wall_time_ms,
            metric_payload=outcome.grade.metric_payload,
            finished_at=outcome.finished_at,
        )

    logger.info(
        "record_run: persisted run %s (%d problems, %d dispatches, winners=%d)",
        run.run_id,
        len(run.problem_graph.problems),
        len(rows_to_record),
        len(run.outcomes),
    )
