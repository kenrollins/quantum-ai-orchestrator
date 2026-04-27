"""Mission Assignment Formulator: Problem → BackendInput for QUBO assignment.

Generates a QUBO matrix for the assignment problem:
- Minimize cost of assigning assets to tasks
- Respect capacity constraints
- Each task must be assigned exactly once
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from orchestrator.pipeline.types import BackendInput, Problem, ProblemClass

logger = logging.getLogger(__name__)

# Default parameters
DEFAULT_ASSETS = 8
DEFAULT_TASKS = 6
DEFAULT_CAPACITY = 2
DEFAULT_SEED = 42


def _generate_cost_matrix(
    num_assets: int,
    num_tasks: int,
    seed: int | None = None,
) -> np.ndarray:
    """Generate random cost matrix for assignment.

    Args:
        num_assets: Number of assets (workers/vehicles/etc).
        num_tasks: Number of tasks to assign.
        seed: Random seed for reproducibility.

    Returns:
        Cost matrix of shape (num_assets, num_tasks).
    """
    rng = np.random.default_rng(seed)
    # Costs in range [1, 100]
    costs = rng.integers(1, 100, size=(num_assets, num_tasks))
    return costs


def _build_qubo(
    cost_matrix: np.ndarray,
    capacity: int,
    penalty_scale: float = 100.0,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Build QUBO matrix for assignment problem.

    Binary variables: x[i,j] = 1 if asset i is assigned to task j.
    Flattened index: k = i * num_tasks + j

    Objective: min sum_ij cost[i,j] * x[i,j]
    Constraints:
    - Each task assigned exactly once: sum_i x[i,j] = 1
    - Each asset at most 'capacity' tasks: sum_j x[i,j] <= capacity

    Args:
        cost_matrix: Assignment costs (num_assets, num_tasks).
        capacity: Max tasks per asset.
        penalty_scale: Lagrange multiplier for constraints.

    Returns:
        Tuple of (QUBO matrix, metadata dict).
    """
    num_assets, num_tasks = cost_matrix.shape
    num_vars = num_assets * num_tasks

    # Initialize QUBO (upper triangular)
    Q = np.zeros((num_vars, num_vars))

    # Add objective (diagonal)
    for i in range(num_assets):
        for j in range(num_tasks):
            k = i * num_tasks + j
            Q[k, k] += cost_matrix[i, j]

    # Add constraint: each task assigned exactly once
    # (sum_i x[i,j] - 1)^2 = sum_i x[i,j]^2 - 2*sum_i x[i,j] + 1
    #                     = sum_i x[i,j] - 2*sum_i x[i,j] + 1 + 2*sum_{i<i'} x[i,j]*x[i',j]
    for j in range(num_tasks):
        # Linear terms (diagonal): -1 per variable (from -2*x + x^2 = -x for binary)
        for i in range(num_assets):
            k = i * num_tasks + j
            Q[k, k] += penalty_scale * (-1)

        # Quadratic terms (off-diagonal): +2 for each pair
        for i1 in range(num_assets):
            for i2 in range(i1 + 1, num_assets):
                k1 = i1 * num_tasks + j
                k2 = i2 * num_tasks + j
                Q[k1, k2] += penalty_scale * 2

    # Add constraint: each asset at most 'capacity' tasks (soft constraint)
    # We use slack variables or penalty for exceeding capacity
    # Simplified: penalize if sum_j x[i,j] > capacity
    # For soft constraint: sum_j sum_{j'!=j} x[i,j]*x[i,j'] >= choose(capacity+1, 2) gets penalized
    if capacity < num_tasks:
        slack_penalty = penalty_scale * 0.5  # Softer penalty for capacity
        for i in range(num_assets):
            for j1 in range(num_tasks):
                for j2 in range(j1 + 1, num_tasks):
                    k1 = i * num_tasks + j1
                    k2 = i * num_tasks + j2
                    # Penalize pairs beyond capacity
                    Q[k1, k2] += slack_penalty / max(1, capacity)

    # Compute theoretical bounds
    min_cost = np.min(cost_matrix, axis=0).sum()  # Best case: cheapest asset for each task
    max_cost = np.max(cost_matrix, axis=0).sum()  # Worst case

    metadata = {
        "num_assets": num_assets,
        "num_tasks": num_tasks,
        "num_vars": num_vars,
        "capacity": capacity,
        "penalty_scale": penalty_scale,
        "cost_matrix": cost_matrix.tolist(),
        "min_cost_bound": float(min_cost),
        "max_cost_bound": float(max_cost),
    }

    return Q, metadata


def formulate(problem: Problem) -> BackendInput:
    """Convert an assignment problem to backend-ready QUBO input.

    Args:
        problem: A Problem with problem_class=QUBO_ASSIGNMENT.

    Returns:
        BackendInput with QUBO matrix and metadata.

    Raises:
        ValueError: If problem_class is not QUBO_ASSIGNMENT.
    """
    if problem.problem_class != ProblemClass.QUBO_ASSIGNMENT:
        raise ValueError(
            f"Assignment formulator received wrong problem class: {problem.problem_class}"
        )

    params = problem.params

    # Extract parameters with defaults
    num_assets = params.get("assets", DEFAULT_ASSETS)
    num_tasks = params.get("tasks", DEFAULT_TASKS)
    capacity = params.get("capacity", DEFAULT_CAPACITY)
    seed = params.get("seed", DEFAULT_SEED)

    logger.info(
        "Formulating assignment problem %s: assets=%d, tasks=%d, capacity=%d",
        problem.problem_id, num_assets, num_tasks, capacity,
    )

    # Generate cost matrix
    cost_matrix = _generate_cost_matrix(num_assets, num_tasks, seed)

    # Build QUBO
    Q, qubo_metadata = _build_qubo(cost_matrix, capacity)

    # Package for backends
    payload = {
        "problem_type": "qubo_assignment",
        "qubo_matrix": Q.tolist(),
        "metadata": qubo_metadata,
        "config": {
            "assets": num_assets,
            "tasks": num_tasks,
            "capacity": capacity,
            "seed": seed,
        },
    }

    return BackendInput(problem=problem, payload=payload)
