"""Mission Assignment Evaluator: Score QUBO solutions.

Quality metric: normalized objective value (higher is better).
quality = 1 - (obj - min_bound) / (max_bound - min_bound)
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from orchestrator.pipeline.types import Grade, Problem, Solution

logger = logging.getLogger(__name__)


def _decode_assignment(
    sample: np.ndarray,
    num_assets: int,
    num_tasks: int,
) -> dict[int, int]:
    """Decode binary sample to task->asset assignment.

    Args:
        sample: Binary vector of length num_assets * num_tasks.
        num_assets: Number of assets.
        num_tasks: Number of tasks.

    Returns:
        Dict mapping task index to assigned asset index.
    """
    assignments = {}
    for j in range(num_tasks):
        for i in range(num_assets):
            k = i * num_tasks + j
            if k < len(sample) and sample[k] == 1:
                if j not in assignments:
                    assignments[j] = i
                # If multiple assets assigned to same task, take first
    return assignments


def _compute_objective(
    sample: np.ndarray,
    cost_matrix: np.ndarray,
    num_tasks: int,
) -> float:
    """Compute objective value for a sample.

    Args:
        sample: Binary solution vector.
        cost_matrix: Cost matrix (num_assets, num_tasks).
        num_tasks: Number of tasks.

    Returns:
        Total assignment cost.
    """
    num_assets = cost_matrix.shape[0]
    total_cost = 0.0

    for i in range(num_assets):
        for j in range(num_tasks):
            k = i * num_tasks + j
            if k < len(sample) and sample[k] == 1:
                total_cost += cost_matrix[i, j]

    return total_cost


def _check_feasibility(
    sample: np.ndarray,
    num_assets: int,
    num_tasks: int,
    capacity: int,
) -> tuple[bool, list[str]]:
    """Check if solution satisfies constraints.

    Args:
        sample: Binary solution vector.
        num_assets: Number of assets.
        num_tasks: Number of tasks.
        capacity: Max tasks per asset.

    Returns:
        Tuple of (is_feasible, list of violation messages).
    """
    violations = []

    # Check each task is assigned exactly once
    for j in range(num_tasks):
        assigned_count = 0
        for i in range(num_assets):
            k = i * num_tasks + j
            if k < len(sample) and sample[k] == 1:
                assigned_count += 1
        if assigned_count == 0:
            violations.append(f"Task {j} is not assigned")
        elif assigned_count > 1:
            violations.append(f"Task {j} is assigned to {assigned_count} assets")

    # Check capacity constraints
    for i in range(num_assets):
        task_count = 0
        for j in range(num_tasks):
            k = i * num_tasks + j
            if k < len(sample) and sample[k] == 1:
                task_count += 1
        if task_count > capacity:
            violations.append(f"Asset {i} exceeds capacity ({task_count} > {capacity})")

    return len(violations) == 0, violations


def evaluate(problem: Problem, solution: Solution) -> Grade:
    """Score an assignment solution.

    Computes objective value and normalizes to quality score.
    Penalizes infeasible solutions.

    Args:
        problem: The original assignment problem.
        solution: The solver's solution.

    Returns:
        Grade with quality, wall_time, and metrics.
    """
    logger.info(
        "Evaluating assignment solution from %s for problem %s",
        solution.backend_name,
        problem.problem_id,
    )

    payload = solution.payload
    metrics: dict[str, Any] = {
        "backend": solution.backend_name,
        "success": solution.success,
    }

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
            metric_payload={"error": solution.error, **metrics},
        )

    # Extract solution and metadata
    sample = payload.get("sample")
    if sample is None:
        sample = payload.get("solution")
    qubo_metadata = payload.get("metadata", {})

    if sample is None:
        logger.error("Solution missing 'sample' field")
        return Grade(
            quality=0.0,
            wall_time_ms=solution.wall_time_ms,
            metric_payload={"error": "Missing sample", **metrics},
        )

    # Convert to numpy
    if not isinstance(sample, np.ndarray):
        sample = np.array(sample)

    # Get problem parameters
    num_assets = qubo_metadata.get("num_assets", problem.params.get("assets", 8))
    num_tasks = qubo_metadata.get("num_tasks", problem.params.get("tasks", 6))
    capacity = qubo_metadata.get("capacity", problem.params.get("capacity", 2))
    cost_matrix = qubo_metadata.get("cost_matrix")
    min_bound = qubo_metadata.get("min_cost_bound", 0)
    max_bound = qubo_metadata.get("max_cost_bound", 1)

    if cost_matrix is not None:
        cost_matrix = np.array(cost_matrix)
    else:
        # Can't evaluate without cost matrix
        logger.error("Solution missing cost_matrix in metadata")
        return Grade(
            quality=0.0,
            wall_time_ms=solution.wall_time_ms,
            metric_payload={"error": "Missing cost_matrix", **metrics},
        )

    # Check feasibility
    is_feasible, violations = _check_feasibility(sample, num_assets, num_tasks, capacity)

    # Compute objective
    objective = _compute_objective(sample, cost_matrix, num_tasks)

    # Decode assignment
    assignment = _decode_assignment(sample, num_assets, num_tasks)

    # Compute quality (normalized, penalize infeasibility)
    if max_bound > min_bound:
        raw_quality = 1.0 - (objective - min_bound) / (max_bound - min_bound)
        raw_quality = max(0.0, min(1.0, raw_quality))
    else:
        raw_quality = 1.0 if objective <= min_bound else 0.0

    # Penalize infeasible solutions
    feasibility_penalty = 0.0 if is_feasible else 0.5
    quality = max(0.0, raw_quality - feasibility_penalty)

    metrics.update({
        "objective": objective,
        "min_bound": min_bound,
        "max_bound": max_bound,
        "raw_quality": raw_quality,
        "is_feasible": is_feasible,
        "violations": violations,
        "assignment": assignment,
        "tasks_assigned": len(assignment),
        "tasks_total": num_tasks,
        # Echo dimensions + cost matrix back to the dashboard so the bipartite
        # panel can render edge labels without re-querying the formulator.
        "num_assets": num_assets,
        "num_tasks": num_tasks,
        "capacity": capacity,
        "cost_matrix": cost_matrix.tolist() if cost_matrix is not None else None,
    })

    logger.info(
        "Assignment evaluation: backend=%s, obj=%.1f, quality=%.4f, feasible=%s",
        solution.backend_name, objective, quality, is_feasible,
    )

    return Grade(
        quality=quality,
        wall_time_ms=solution.wall_time_ms,
        metric_payload=metrics,
    )
