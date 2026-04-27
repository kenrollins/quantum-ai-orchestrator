"""Formulator: Problem → Backend-ready input.

Pure router that dispatches each leaf problem to the appropriate
skill-specific formulator based on problem_class.
"""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING, Protocol

from .types import BackendInput, Problem, ProblemClass

if TYPE_CHECKING:
    from typing import Callable

logger = logging.getLogger(__name__)


class SkillFormulator(Protocol):
    """Protocol for skill-specific formulators."""

    def formulate(self, problem: Problem) -> BackendInput:
        """Convert a problem to backend-ready input."""
        ...


# Registry mapping problem_class to skill module path
SKILL_FORMULATORS: dict[ProblemClass, str] = {
    ProblemClass.QEC_SYNDROME: "skills.qec_decode.formulator",
    ProblemClass.QUBO_ASSIGNMENT: "skills.mission_assignment.formulator",
    ProblemClass.QUBO_ROUTING: "skills.routing.formulator",
    ProblemClass.QUBO_PORTFOLIO: "skills.portfolio.formulator",
}


def _load_formulator(problem_class: ProblemClass) -> SkillFormulator:
    """Dynamically load the skill formulator module."""
    module_path = SKILL_FORMULATORS.get(problem_class)
    if module_path is None:
        raise ValueError(f"No formulator registered for {problem_class}")

    try:
        module = importlib.import_module(module_path)
        return module  # type: ignore[return-value]
    except ImportError as e:
        raise ImportError(f"Failed to load formulator for {problem_class}: {e}") from e


def formulate(problem: Problem) -> BackendInput:
    """Convert a problem to backend-ready input.

    Dispatches to the skill-specific formulator based on problem_class.

    Args:
        problem: A Problem node from the decomposed graph.

    Returns:
        BackendInput ready for dispatch to backends.

    Raises:
        ValueError: If no formulator is registered for the problem class.
        ImportError: If the skill formulator module fails to load.
    """
    logger.info(
        "Formulating problem_id=%s class=%s",
        problem.problem_id,
        problem.problem_class.value,
    )

    formulator = _load_formulator(problem.problem_class)
    backend_input = formulator.formulate(problem)

    logger.debug(
        "Formulated: payload keys=%s",
        list(backend_input.payload.keys()),
    )

    return backend_input


def formulate_leaves(problems: list[Problem]) -> list[BackendInput]:
    """Formulate all leaf problems in a graph.

    Args:
        problems: List of Problem nodes (typically the leaves of a ProblemGraph).

    Returns:
        List of BackendInputs, one per problem.
    """
    return [formulate(p) for p in problems]
