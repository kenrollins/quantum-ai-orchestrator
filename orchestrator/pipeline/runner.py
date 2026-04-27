"""Runner: Orchestrate the full pipeline from ask to answer.

This is the main entry point for executing a natural language ask
through all six pipeline stages.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import time
from datetime import datetime, timezone
from uuid import UUID, uuid4

from .decomposer import decompose
from .dispatcher import dispatch
from .evaluator import evaluate, pick_winner
from .formulator import formulate
from .reassembler import reassemble
from .types import (
    BackendChoice,
    BackendInput,
    Grade,
    Outcome,
    Problem,
    Run,
    RunStatus,
    Solution,
)

logger = logging.getLogger(__name__)


_BACKEND_MODULE_ROOT = "orchestrator.quantum.backends"


def _load_backend_module(name: str):
    """Dynamically import a backend module by name."""
    return importlib.import_module(f"{_BACKEND_MODULE_ROOT}.{name}")


async def _execute_backend(
    backend_choice: BackendChoice,
    backend_input: BackendInput,
) -> Solution:
    """Run a backend on a thread (so blocking solvers don't stall the event loop).

    Each backend module is expected to expose:

        def run(backend_input: BackendInput, gpu_lane: int | None = None) -> Solution

    Failures (import errors, exceptions inside `run`) are converted to a
    Solution(success=False) so callers don't need to handle exceptions.
    """
    backend = backend_choice.backend
    start_time = time.perf_counter()

    try:
        module = _load_backend_module(backend.name)
    except ImportError as e:
        wall_time_ms = int((time.perf_counter() - start_time) * 1000)
        logger.exception("Backend %s import failed", backend.name)
        return Solution(
            backend_name=backend.name,
            payload={},
            wall_time_ms=wall_time_ms,
            success=False,
            error=f"Import failed: {e}",
        )

    run_fn = getattr(module, "run", None)
    if run_fn is None:
        return Solution(
            backend_name=backend.name,
            payload={},
            wall_time_ms=int((time.perf_counter() - start_time) * 1000),
            success=False,
            error=f"Backend module {backend.name} has no run() function",
        )

    try:
        # Run blocking solver in a thread so we can race multiple backends concurrently.
        solution = await asyncio.to_thread(
            run_fn, backend_input, backend_choice.gpu_lane
        )
    except Exception as e:
        wall_time_ms = int((time.perf_counter() - start_time) * 1000)
        logger.exception("Backend %s raised", backend.name)
        return Solution(
            backend_name=backend.name,
            payload={},
            wall_time_ms=wall_time_ms,
            success=False,
            error=str(e),
        )

    return solution


async def _dispatch_and_race(
    problem: Problem,
    backend_input: BackendInput,
    top_k: int = 3,
    phase: int = 1,
) -> tuple[Outcome, list[Outcome]]:
    """Dispatch a problem to multiple backends and race them in parallel.

    Returns:
        (winner_outcome, all_outcomes) — `all_outcomes` includes every
        (problem, backend) pair we dispatched, in dispatch order. The
        winner is also the first element matching backend_name in the list.
    """
    choices = await dispatch(backend_input, top_k=top_k, phase=phase)

    logger.info(
        "Racing %d backend(s) for problem %s",
        len(choices),
        problem.problem_id,
    )

    dispatched_at = datetime.now(timezone.utc)

    # Execute all backends in parallel (each blocking solver runs on its own thread)
    tasks = [_execute_backend(choice, backend_input) for choice in choices]
    solutions = await asyncio.gather(*tasks, return_exceptions=True)

    # Convert exceptions to failed solutions
    processed_solutions: list[Solution] = []
    for i, result in enumerate(solutions):
        if isinstance(result, BaseException):
            processed_solutions.append(
                Solution(
                    backend_name=choices[i].backend.name,
                    payload={},
                    wall_time_ms=0,
                    success=False,
                    error=str(result),
                )
            )
        elif isinstance(result, Solution):
            processed_solutions.append(result)
        else:
            processed_solutions.append(
                Solution(
                    backend_name=choices[i].backend.name,
                    payload={},
                    wall_time_ms=0,
                    success=False,
                    error=f"Unexpected result type: {type(result)}",
                )
            )

    # Evaluate every backend's solution and build a stable Outcome per dispatch
    grades: list[tuple[BackendChoice, Solution, Grade]] = []
    all_outcomes: list[Outcome] = []
    finished_at = datetime.now(timezone.utc)
    for choice, solution in zip(choices, processed_solutions):
        grade = evaluate(problem, solution)
        grades.append((choice, solution, grade))
        all_outcomes.append(
            Outcome(
                dispatch_id=uuid4(),
                problem=problem,
                backend_choice=choice,
                solution=solution,
                grade=grade,
                dispatched_at=dispatched_at,
                finished_at=finished_at,
            )
        )

    winner = pick_winner(grades)

    if winner is None:
        # All backends failed — flag the first dispatch as the "winner" placeholder
        # so downstream still has something to render. Race history reflects truth.
        return all_outcomes[0], all_outcomes

    winning_choice, _, _ = winner
    # Find the matching outcome in all_outcomes — its dispatch_id is what we want.
    winner_outcome = next(
        o for o in all_outcomes if o.backend_choice.backend.name == winning_choice.backend.name
    )
    return winner_outcome, all_outcomes


async def run_pipeline(
    ask: str,
    run_id: UUID | None = None,
    top_k: int = 3,
    phase: int = 1,
) -> Run:
    """Execute the full pipeline for a natural language ask.

    Stages:
    1. Decompose: NL ask → problem graph
    2. Formulate: problems → backend-ready inputs
    3. Dispatch + Execute: race backends for each leaf
    4. Evaluate: score solutions
    5. Reassemble: combine results into final answer

    Args:
        ask: Natural language description of the problem.
        run_id: UUID for this run (generated if not provided).
        top_k: Maximum backends to race per problem.
        phase: Maximum backend phase to include.

    Returns:
        Run object with the full result.
    """
    if run_id is None:
        run_id = uuid4()

    logger.info("Starting pipeline run %s", run_id)

    # Initialize run
    run = Run(
        run_id=run_id,
        ask_text=ask,
        skill="unknown",
        status=RunStatus.RUNNING,
    )

    # Best-effort: record run start in Postgres. Failures here don't abort
    # the pipeline — provenance is nice-to-have, not blocking.
    _record_start_safe(run)

    try:
        # Stage 1: Decompose
        logger.info("Stage 1: Decomposing ask")
        graph = await decompose(ask, run_id)
        run.skill = graph.skill
        run.problem_graph = graph

        # Stage 2: Formulate leaves
        logger.info("Stage 2: Formulating %d leaf problem(s)", len(graph.leaves))
        backend_inputs = []
        for leaf in graph.leaves:
            backend_input = formulate(leaf)
            backend_inputs.append((leaf, backend_input))

        # Stage 3+4: Dispatch, execute, and evaluate
        logger.info("Stage 3+4: Dispatching and racing backends")
        outcome_tasks = [
            _dispatch_and_race(problem, bi, top_k, phase)
            for problem, bi in backend_inputs
        ]
        results = await asyncio.gather(*outcome_tasks)
        run.outcomes = [winner for winner, _ in results]
        # Flatten all-participant lists into one race_history.
        run.race_history = [o for _, all_o in results for o in all_o]

        # Stage 5: Reassemble
        logger.info("Stage 5: Reassembling final answer")
        final_answer = reassemble(graph, run.outcomes)
        run.final_answer = final_answer

        # Mark success
        run.status = RunStatus.SUCCEEDED
        run.finished_at = datetime.now(timezone.utc)

        logger.info(
            "Pipeline run %s completed: skill=%s, problems_solved=%d/%d",
            run_id,
            run.skill,
            final_answer.get("problems_solved", 0),
            final_answer.get("problems_total", 0),
        )

    except Exception as e:
        logger.exception("Pipeline run %s failed", run_id)
        run.status = RunStatus.FAILED
        run.error = str(e)
        run.finished_at = datetime.now(timezone.utc)

    _record_finish_safe(run)
    return run


def _record_start_safe(run: Run) -> None:
    """Insert run-start row into Postgres, swallowing failures."""
    try:
        from orchestrator.storage import record_run_start
        record_run_start(run)
    except Exception:
        logger.warning("Provenance write (start) failed for run %s", run.run_id, exc_info=True)


def _record_finish_safe(run: Run) -> None:
    """Persist completed run + outcomes to Postgres, swallowing failures."""
    try:
        from orchestrator.storage import record_run
        record_run(run)
    except Exception:
        logger.warning("Provenance write (finish) failed for run %s", run.run_id, exc_info=True)


def run_pipeline_sync(
    ask: str,
    run_id: UUID | None = None,
    top_k: int = 3,
    phase: int = 1,
) -> Run:
    """Synchronous wrapper for run_pipeline()."""
    return asyncio.run(run_pipeline(ask, run_id, top_k, phase))
