"""QEC Decode Evaluator: Score decoder solutions by Logical Error Rate.

Quality metric: 1 - LER (higher is better, max 1.0 means no logical errors).
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from orchestrator.pipeline.types import Grade, Problem, Solution

logger = logging.getLogger(__name__)


def _compute_ler(
    predictions: np.ndarray,
    observable_flips: np.ndarray,
) -> float:
    """Compute Logical Error Rate.

    Args:
        predictions: Decoder's predicted observable flips (shots,) or (shots, n_obs).
        observable_flips: Ground truth observable flips from Stim.

    Returns:
        Logical Error Rate (0.0 to 1.0).
    """
    # Ensure both are 2D
    if predictions.ndim == 1:
        predictions = predictions.reshape(-1, 1)
    if observable_flips.ndim == 1:
        observable_flips = observable_flips.reshape(-1, 1)

    # XOR to find mismatches
    errors = np.logical_xor(predictions, observable_flips)

    # A shot is a logical error if any observable is wrong
    shot_errors = np.any(errors, axis=1)

    ler = float(np.mean(shot_errors))
    return ler


def evaluate(problem: Problem, solution: Solution) -> Grade:
    """Score a QEC decoder solution.

    Computes Logical Error Rate and converts to quality score.
    Quality = 1 - LER (perfect decoding = 1.0).

    Args:
        problem: The original QEC problem.
        solution: The decoder's solution with predictions.

    Returns:
        Grade with quality, wall_time, and metrics.
    """
    logger.info(
        "Evaluating QEC solution from %s for problem %s",
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

    # Extract predictions and ground truth
    predictions = payload.get("predictions")
    observable_flips = payload.get("observable_flips")

    if predictions is None:
        logger.error("Solution missing 'predictions' field")
        return Grade(
            quality=0.0,
            wall_time_ms=solution.wall_time_ms,
            metric_payload={"error": "Missing predictions", **metrics},
        )

    if observable_flips is None:
        # Try to get from problem payload
        problem_payload = getattr(problem, "params", {})
        # This would need to come from the original input
        logger.error("Solution missing 'observable_flips' for comparison")
        return Grade(
            quality=0.0,
            wall_time_ms=solution.wall_time_ms,
            metric_payload={"error": "Missing ground truth", **metrics},
        )

    # Convert to numpy arrays if needed
    if not isinstance(predictions, np.ndarray):
        predictions = np.array(predictions)
    if not isinstance(observable_flips, np.ndarray):
        observable_flips = np.array(observable_flips)

    # Compute LER
    ler = _compute_ler(predictions, observable_flips)
    quality = 1.0 - ler

    # Additional metrics
    shots = len(predictions)
    logical_errors = int(ler * shots)

    metrics.update({
        "ler": ler,
        "quality": quality,
        "shots": shots,
        "logical_errors": logical_errors,
        "decode_time_ms": payload.get("decode_time_ms", solution.wall_time_ms),
    })

    logger.info(
        "QEC evaluation: backend=%s, LER=%.4f, quality=%.4f, shots=%d",
        solution.backend_name, ler, quality, shots,
    )

    return Grade(
        quality=quality,
        wall_time_ms=solution.wall_time_ms,
        metric_payload=metrics,
    )
