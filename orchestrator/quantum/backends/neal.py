"""Neal backend: D-Wave simulated annealing for QUBO assignment.

Wraps `neal.SimulatedAnnealingSampler`. Reads the QUBO matrix the
formulator built (with Lagrangian penalties baked in) and returns the
lowest-energy sample. CPU-only.
"""

from __future__ import annotations

import logging

import numpy as np

from orchestrator.pipeline.types import BackendInput, Solution

from .base import failed_solution, timed

logger = logging.getLogger(__name__)

BACKEND_NAME = "neal"
DEFAULT_NUM_READS = 200
DEFAULT_SWEEPS = 1000


def _qubo_matrix_to_dict(Q: np.ndarray) -> dict[tuple[int, int], float]:
    """Convert dense upper-triangular QUBO to dimod's dict form."""
    n = Q.shape[0]
    out: dict[tuple[int, int], float] = {}
    for i in range(n):
        if Q[i, i] != 0:
            out[(i, i)] = float(Q[i, i])
        for j in range(i + 1, n):
            if Q[i, j] != 0:
                out[(i, j)] = float(Q[i, j])
    return out


def run(
    backend_input: BackendInput,
    gpu_lane: int | None = None,
) -> Solution:
    """Solve a QUBO with neal simulated annealing.

    Args:
        backend_input: Must carry `qubo_matrix` and `metadata` (cost matrix etc).
        gpu_lane: Ignored. Neal is CPU-only.
    """
    _ = gpu_lane

    try:
        import neal
    except ImportError as e:
        return failed_solution(BACKEND_NAME, f"Missing dependency: {e}")

    payload = backend_input.payload
    qubo_matrix = payload.get("qubo_matrix")
    metadata = payload.get("metadata", {})
    config = payload.get("config", {})

    if qubo_matrix is None:
        return failed_solution(BACKEND_NAME, "Missing qubo_matrix in payload")

    Q = np.asarray(qubo_matrix, dtype=float)
    num_reads = config.get("num_reads", DEFAULT_NUM_READS)
    num_sweeps = config.get("num_sweeps", DEFAULT_SWEEPS)

    with timed() as t:
        try:
            qubo_dict = _qubo_matrix_to_dict(Q)
            sampler = neal.SimulatedAnnealingSampler()
            sampleset = sampler.sample_qubo(
                qubo_dict,
                num_reads=num_reads,
                num_sweeps=num_sweeps,
                seed=config.get("seed", 42),
            )
            best = sampleset.first
            sample_dict = best.sample
            energy = float(best.energy)
        except Exception as e:
            logger.exception("neal sample failed")
            return failed_solution(
                BACKEND_NAME,
                f"Sample error: {e}",
                wall_time_ms=t["wall_time_ms"],
            )

    # Extract sample vector in the order expected by the evaluator
    n = Q.shape[0]
    sample = np.zeros(n, dtype=np.uint8)
    for k, v in sample_dict.items():
        if 0 <= int(k) < n:
            sample[int(k)] = 1 if v == 1 else 0

    # Decode assignment for convenience
    num_assets = metadata.get("num_assets", config.get("assets", 0))
    num_tasks = metadata.get("num_tasks", config.get("tasks", 0))
    assignment: dict[int, int] = {}
    for i in range(num_assets):
        for j in range(num_tasks):
            if sample[i * num_tasks + j] == 1 and j not in assignment:
                assignment[j] = i

    # Compute the *true* cost (without penalty terms) so the evaluator
    # has a meaningful objective. The evaluator recomputes from cost_matrix
    # anyway, but keeping it consistent for logs.
    cost_matrix = metadata.get("cost_matrix")
    objective = None
    if cost_matrix is not None:
        cm = np.asarray(cost_matrix)
        objective = 0.0
        for j, i in assignment.items():
            objective += float(cm[i, j])

    logger.info(
        "neal best: energy=%.2f, num_reads=%d, %dms",
        energy,
        num_reads,
        t["wall_time_ms"],
    )

    return Solution(
        backend_name=BACKEND_NAME,
        payload={
            "sample": sample,
            "assignment": assignment,
            "energy": energy,
            "objective": objective,
            "metadata": metadata,
            "num_reads": num_reads,
            "num_sweeps": num_sweeps,
            "solver": "neal_SA",
        },
        wall_time_ms=t["wall_time_ms"],
        success=True,
    )
