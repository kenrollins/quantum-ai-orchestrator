"""Classical OR-Tools backend: CP-SAT solver for QUBO assignment.

This backend treats the assignment problem natively (not via QUBO matrix):
- Binary decision vars x[i,j] for each (asset, task) pair
- Hard constraints for "each task assigned exactly once" and capacity
- Objective: minimize sum cost[i,j] * x[i,j]

It still emits a sample vector matching the QUBO encoding so the
evaluator can score it the same way as quantum/annealing backends.
"""

from __future__ import annotations

import logging

import numpy as np

from orchestrator.pipeline.types import BackendInput, Solution

from .base import failed_solution, timed

logger = logging.getLogger(__name__)

BACKEND_NAME = "classical_ortools"
DEFAULT_TIME_LIMIT_S = 5.0


def run(
    backend_input: BackendInput,
    gpu_lane: int | None = None,
) -> Solution:
    """Solve the assignment problem with OR-Tools CP-SAT.

    Args:
        backend_input: Must carry `metadata.cost_matrix`, plus assets/tasks/capacity.
        gpu_lane: Ignored. CP-SAT is CPU-only.

    Returns:
        Solution with sample vector + decoded assignment.
    """
    _ = gpu_lane

    try:
        from ortools.sat.python import cp_model
    except ImportError as e:
        return failed_solution(BACKEND_NAME, f"Missing dependency: {e}")

    payload = backend_input.payload
    metadata = payload.get("metadata", {})
    config = payload.get("config", {})

    cost_matrix = metadata.get("cost_matrix")
    num_assets = metadata.get("num_assets") or config.get("assets")
    num_tasks = metadata.get("num_tasks") or config.get("tasks")
    capacity = metadata.get("capacity") or config.get("capacity")

    if cost_matrix is None or num_assets is None or num_tasks is None:
        return failed_solution(
            BACKEND_NAME,
            "Missing cost_matrix or dimensions in payload",
        )

    cost_matrix = np.asarray(cost_matrix)

    with timed() as t:
        try:
            model = cp_model.CpModel()

            x = {}
            for i in range(num_assets):
                for j in range(num_tasks):
                    x[(i, j)] = model.NewBoolVar(f"x_{i}_{j}")

            # Each task assigned exactly once
            for j in range(num_tasks):
                model.Add(sum(x[(i, j)] for i in range(num_assets)) == 1)

            # Capacity
            if capacity is not None and capacity < num_tasks:
                for i in range(num_assets):
                    model.Add(sum(x[(i, j)] for j in range(num_tasks)) <= capacity)

            # Objective
            model.Minimize(
                sum(int(cost_matrix[i, j]) * x[(i, j)]
                    for i in range(num_assets)
                    for j in range(num_tasks))
            )

            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = DEFAULT_TIME_LIMIT_S
            status = solver.Solve(model)

            if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                return failed_solution(
                    BACKEND_NAME,
                    f"CP-SAT returned status {solver.StatusName(status)}",
                    wall_time_ms=t["wall_time_ms"],
                )

            # Extract sample in QUBO encoding
            sample = np.zeros(num_assets * num_tasks, dtype=np.uint8)
            assignment: dict[int, int] = {}
            for i in range(num_assets):
                for j in range(num_tasks):
                    if solver.Value(x[(i, j)]) == 1:
                        sample[i * num_tasks + j] = 1
                        assignment[j] = i

            objective = float(solver.ObjectiveValue())
            is_optimal = status == cp_model.OPTIMAL

        except Exception as e:
            logger.exception("OR-Tools solve failed")
            return failed_solution(
                BACKEND_NAME,
                f"Solve error: {e}",
                wall_time_ms=t["wall_time_ms"],
            )

    logger.info(
        "OR-Tools solved (%s) in %dms, obj=%.1f",
        "OPTIMAL" if is_optimal else "FEASIBLE",
        t["wall_time_ms"],
        objective,
    )

    return Solution(
        backend_name=BACKEND_NAME,
        payload={
            "sample": sample,
            "assignment": assignment,
            "objective": objective,
            "is_optimal": is_optimal,
            "metadata": metadata,
            "solver": "CP-SAT",
        },
        wall_time_ms=t["wall_time_ms"],
        success=True,
    )
