"""PyMatching backend: classical MWPM decoder for QEC syndromes.

Reads detection events + DEM from the formulator's payload, produces
predicted observable flips. Propagates ground-truth observable_flips
back to the evaluator (the evaluator XORs predictions vs. truth to
compute LER).
"""

from __future__ import annotations

import logging

import numpy as np

from orchestrator.pipeline.types import BackendInput, Solution

from .base import failed_solution, timed

logger = logging.getLogger(__name__)

BACKEND_NAME = "pymatching"


def run(
    backend_input: BackendInput,
    gpu_lane: int | None = None,
) -> Solution:
    """Decode syndromes with PyMatching.

    Args:
        backend_input: Must carry a `syndrome` dict in payload with
            `detection_events`, `observable_flips`, and `dem_str`.
        gpu_lane: Ignored. PyMatching is CPU-only.

    Returns:
        Solution with predictions + ground-truth observable_flips.
    """
    _ = gpu_lane  # Unused; PyMatching is CPU-only.

    try:
        import pymatching
        import stim
    except ImportError as e:
        return failed_solution(
            BACKEND_NAME,
            f"Missing dependency: {e}",
        )

    payload = backend_input.payload
    syndrome = payload.get("syndrome", {})

    detection_events = syndrome.get("detection_events")
    observable_flips = syndrome.get("observable_flips")
    dem_str = syndrome.get("dem_str")

    if detection_events is None or dem_str is None:
        return failed_solution(
            BACKEND_NAME,
            "Missing detection_events or dem_str in syndrome payload",
        )

    if not isinstance(detection_events, np.ndarray):
        detection_events = np.asarray(detection_events, dtype=np.uint8)

    with timed() as t:
        try:
            dem = stim.DetectorErrorModel(dem_str)
            matching = pymatching.Matching.from_detector_error_model(dem)
            predictions = matching.decode_batch(detection_events)
        except Exception as e:
            logger.exception("PyMatching decode failed")
            return failed_solution(
                BACKEND_NAME,
                f"Decode error: {e}",
                wall_time_ms=t["wall_time_ms"],
            )

    predictions = np.asarray(predictions, dtype=np.uint8)

    logger.info(
        "PyMatching decoded %d shots in %dms",
        len(predictions),
        t["wall_time_ms"],
    )

    return Solution(
        backend_name=BACKEND_NAME,
        payload={
            "predictions": predictions,
            "observable_flips": observable_flips,
            "decode_time_ms": t["wall_time_ms"],
            "decoder": "MWPM",
            "shots": int(len(predictions)),
        },
        wall_time_ms=t["wall_time_ms"],
        success=True,
    )
