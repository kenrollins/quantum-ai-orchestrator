"""Reassembler: Walk the problem graph bottom-up to produce the final answer.

For single-leaf graphs (most Phase 1 asks), this is trivial.
For multi-problem DAGs, it combines child results according to the skill's logic.
"""

from __future__ import annotations

import logging
from typing import Any

from .types import Outcome, Problem, ProblemGraph

logger = logging.getLogger(__name__)


def _build_child_map(graph: ProblemGraph) -> dict[str | None, list[Problem]]:
    """Build a map from parent_id to list of child problems."""
    child_map: dict[str | None, list[Problem]] = {}
    for problem in graph.problems:
        parent = problem.parent_id
        if parent not in child_map:
            child_map[parent] = []
        child_map[parent].append(problem)
    return child_map




def reassemble(
    graph: ProblemGraph,
    outcomes: list[Outcome],
) -> dict[str, Any]:
    """Walk the problem graph bottom-up and produce the final answer.

    For Phase 1 (single-leaf graphs), this simply returns the winning
    solution's payload. For multi-problem DAGs, it combines results
    according to the skill's aggregation logic.

    Args:
        graph: The original problem graph from the decomposer.
        outcomes: List of Outcomes, one per dispatched problem.

    Returns:
        Final answer dictionary with:
        - skill: The skill that handled this ask
        - problems_solved: Count of successfully solved problems
        - problems_total: Total problem count
        - answer: The primary answer (solution payload or aggregation)
        - metadata: Additional info (wall_time, backend used, etc.)

    Raises:
        ValueError: If no outcomes are provided.
    """
    if not outcomes:
        raise ValueError("No outcomes to reassemble")

    logger.info(
        "Reassembling %d outcome(s) for skill=%s",
        len(outcomes),
        graph.skill,
    )

    # Build index for fast lookup
    outcome_by_problem: dict[str, Outcome] = {
        o.problem.problem_id: o for o in outcomes
    }

    # For Phase 1: single-leaf graphs
    if len(graph.problems) == 1:
        problem = graph.problems[0]
        outcome = outcome_by_problem.get(problem.problem_id)

        if outcome is None:
            return {
                "skill": graph.skill,
                "problems_solved": 0,
                "problems_total": 1,
                "answer": None,
                "error": "No outcome for problem",
                "metadata": {},
            }

        return {
            "skill": graph.skill,
            "problems_solved": 1 if outcome.solution.success else 0,
            "problems_total": 1,
            "answer": outcome.solution.payload,
            "metadata": {
                "backend": outcome.backend_choice.backend.name,
                "wall_time_ms": outcome.solution.wall_time_ms,
                "quality": outcome.grade.quality,
                "gpu_lane": outcome.backend_choice.gpu_lane,
            },
        }

    # For multi-problem DAGs: aggregate bottom-up
    # Build child map for traversal (will be used for proper DAG walking in Phase 2+)
    _ = _build_child_map(graph)  # Reserved for future DAG aggregation
    root = graph.root

    if root is None:
        # All problems have parents — malformed graph
        logger.error("No root problem found in graph")
        return {
            "skill": graph.skill,
            "problems_solved": 0,
            "problems_total": len(graph.problems),
            "answer": None,
            "error": "Malformed problem graph: no root",
            "metadata": {},
        }

    # Aggregate all leaf outcomes
    leaves = graph.leaves
    leaf_outcomes = [outcome_by_problem.get(p.problem_id) for p in leaves]
    successful_outcomes = [o for o in leaf_outcomes if o is not None and o.solution.success]

    # Compute aggregate metrics
    total_wall_time = sum(
        o.solution.wall_time_ms for o in successful_outcomes
    )
    avg_quality = (
        sum(o.grade.quality for o in successful_outcomes) / len(successful_outcomes)
        if successful_outcomes
        else 0.0
    )

    # Collect all solution payloads
    leaf_answers = [
        {
            "problem_id": o.problem.problem_id,
            "backend": o.backend_choice.backend.name,
            "payload": o.solution.payload,
            "quality": o.grade.quality,
        }
        for o in successful_outcomes
    ]

    return {
        "skill": graph.skill,
        "problems_solved": len(successful_outcomes),
        "problems_total": len(leaves),
        "answer": {
            "aggregated": True,
            "leaf_results": leaf_answers,
        },
        "metadata": {
            "total_wall_time_ms": total_wall_time,
            "avg_quality": avg_quality,
            "backends_used": list({o.backend_choice.backend.name for o in successful_outcomes}),
        },
    }
