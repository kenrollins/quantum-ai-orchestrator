"""Evaluator: Score backend solutions.

Routes to skill-specific evaluators based on problem_class.
Each evaluator returns a Grade with quality, wall_time_ms, and metric_payload.
"""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING, Protocol

from .types import BackendChoice, Grade, Problem, ProblemClass, Solution

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SkillEvaluator(Protocol):
    """Protocol for skill-specific evaluators."""

    def evaluate(
        self,
        problem: Problem,
        solution: Solution,
    ) -> Grade:
        """Score a solution for a problem.

        Args:
            problem: The original problem.
            solution: The backend's solution.

        Returns:
            Grade with quality score and metrics.
        """
        ...


# Registry mapping problem_class to skill evaluator module path
SKILL_EVALUATORS: dict[ProblemClass, str] = {
    ProblemClass.QEC_SYNDROME: "skills.qec_decode.evaluator",
    ProblemClass.QUBO_ASSIGNMENT: "skills.mission_assignment.evaluator",
    ProblemClass.QUBO_ROUTING: "skills.routing.evaluator",
    ProblemClass.QUBO_PORTFOLIO: "skills.portfolio.evaluator",
}


def _load_evaluator(problem_class: ProblemClass) -> SkillEvaluator:
    """Dynamically load the skill evaluator module."""
    module_path = SKILL_EVALUATORS.get(problem_class)
    if module_path is None:
        raise ValueError(f"No evaluator registered for {problem_class}")

    try:
        module = importlib.import_module(module_path)
        return module  # type: ignore[return-value]
    except ImportError as e:
        raise ImportError(f"Failed to load evaluator for {problem_class}: {e}") from e


def evaluate(
    problem: Problem,
    solution: Solution,
) -> Grade:
    """Score a backend solution.

    Dispatches to the skill-specific evaluator based on problem_class.

    Args:
        problem: The original problem.
        solution: The backend's solution.

    Returns:
        Grade with quality (0.0-1.0), wall_time_ms, and metric_payload.

    Raises:
        ValueError: If no evaluator is registered for the problem class.
        ImportError: If the skill evaluator module fails to load.
    """
    logger.info(
        "Evaluating solution from %s for problem_id=%s",
        solution.backend_name,
        problem.problem_id,
    )

    # Handle failed solutions
    if not solution.success:
        logger.warning(
            "Solution from %s failed: %s",
            solution.backend_name,
            solution.error,
        )
        return Grade(
            quality=0.0,
            wall_time_ms=solution.wall_time_ms,
            metric_payload={"error": solution.error, "success": False},
        )

    evaluator = _load_evaluator(problem.problem_class)
    grade = evaluator.evaluate(problem, solution)

    logger.debug(
        "Graded %s: quality=%.4f wall_time=%dms",
        solution.backend_name,
        grade.quality,
        grade.wall_time_ms,
    )

    return grade


def pick_winner(
    grades: list[tuple[BackendChoice, Solution, Grade]],
) -> tuple[BackendChoice, Solution, Grade] | None:
    """Pick the best solution from a set of graded outcomes.

    Strategy:
    1. Filter out failed solutions (quality == 0)
    2. Sort by quality descending, then by wall_time ascending
    3. Return the best one

    Args:
        grades: List of (backend_choice, solution, grade) tuples.

    Returns:
        The winning (backend_choice, solution, grade) or None if all failed.
    """
    # Filter successes
    successes = [(bc, sol, g) for bc, sol, g in grades if g.quality > 0]

    if not successes:
        logger.warning("All backend solutions failed")
        return None

    # Sort: quality desc, then wall_time asc
    def sort_key(item: tuple[BackendChoice, Solution, Grade]) -> tuple[float, int]:
        _, _, grade = item
        return (-grade.quality, grade.wall_time_ms)

    sorted_grades = sorted(successes, key=sort_key)
    winner = sorted_grades[0]

    logger.info(
        "Winner: %s (quality=%.4f, wall_time=%dms)",
        winner[0].backend.name,
        winner[2].quality,
        winner[2].wall_time_ms,
    )

    return winner
