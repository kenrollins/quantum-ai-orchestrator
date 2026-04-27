"""QEC Decode Formulator: Problem -> BackendInput for syndrome decoding.

Uses NVIDIA's `QCDataPipePreDecoder_Memory_inference` to generate a single
shared dataset that all three QEC backends consume:

- pymatching: uses `detection_events` + `dem_str` (built from MemoryCircuit)
- ising_speed / ising_accuracy: use `trainX` (4, T, D, D) tensor + same
  detection_events and DEM for their PyMatching downstream stage

This way the race is on identical syndromes — no decoder gets an easier
problem than another. NVIDIA's data pipeline is on PYTHONPATH at runtime;
its modules are not vendored.

Default rotation is XV (the only one normalized_weight_mapping_*stab_memory
supports today).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np

from orchestrator.pipeline.types import BackendInput, Problem, ProblemClass

logger = logging.getLogger(__name__)

NVIDIA_ISING_CODE_PATH = Path("/data/models/nvidia-ising/Ising-Decoding/code")

DEFAULT_DISTANCE = 5
DEFAULT_NOISE_RATE = 0.001
DEFAULT_SHOTS = 10_000
DEFAULT_ROUNDS = None  # default: use distance
DEFAULT_BASIS = "X"
DEFAULT_ROTATION = "XV"


def _ensure_nvidia_path() -> None:
    """Prepend NVIDIA's Ising-Decoding code dir to sys.path if not already there."""
    p = str(NVIDIA_ISING_CODE_PATH)
    if not NVIDIA_ISING_CODE_PATH.exists():
        raise FileNotFoundError(
            f"NVIDIA Ising-Decoding code not found at {NVIDIA_ISING_CODE_PATH}. "
            "Run tools/bootstrap_ising.sh."
        )
    if p not in sys.path:
        sys.path.insert(0, p)


def _generate_syndromes(
    distance: int,
    noise_rate: float,
    shots: int,
    rounds: int | None,
    basis: str,
    rotation: str,
) -> dict[str, Any]:
    """Build syndrome data via NVIDIA's MemoryCircuit-based datapipe."""
    _ensure_nvidia_path()
    from data.datapipe_stim import QCDataPipePreDecoder_Memory_inference  # type: ignore

    if rounds is None:
        rounds = distance

    logger.info(
        "QEC data pipeline: d=%d, p=%.2e, shots=%d, rounds=%d, basis=%s, rotation=%s",
        distance, noise_rate, shots, rounds, basis, rotation,
    )

    dp = QCDataPipePreDecoder_Memory_inference(
        distance=distance,
        n_rounds=rounds,
        num_samples=shots,
        error_mode="circuit_level_surface_custom",
        p_error=noise_rate,
        measure_basis=basis,
        code_rotation=rotation,
    )

    stim_circuit = dp.circ.stim_circuit
    num_detectors = stim_circuit.num_detectors
    num_observables = stim_circuit.num_observables
    dem = stim_circuit.detector_error_model(decompose_errors=True)

    detection_events = dp.dets_and_obs[:, :num_detectors].numpy().astype(np.uint8)
    observable_flips = dp.dets_and_obs[:, num_detectors:].numpy().astype(np.uint8)

    return {
        "trainX": dp.trainX_all,                # torch.Tensor (N, 4, T, D, D)
        "detection_events": detection_events,   # np.uint8 (N, num_detectors)
        "observable_flips": observable_flips,   # np.uint8 (N, num_observables)
        "x_syn_diff": dp.x_syn_diff_all,        # torch.Tensor (N, half, T)
        "z_syn_diff": dp.z_syn_diff_all,        # torch.Tensor (N, half, T)
        "dem_str": str(dem),
        "circuit_str": str(stim_circuit),
        "num_detectors": num_detectors,
        "num_observables": num_observables,
        "distance": distance,
        "n_rounds": rounds,
        "noise_rate": noise_rate,
        "shots": shots,
        "basis": basis,
        "rotation": rotation,
    }


def formulate(problem: Problem) -> BackendInput:
    """Convert a QEC syndrome problem to backend-ready input."""
    if problem.problem_class != ProblemClass.QEC_SYNDROME:
        raise ValueError(
            f"QEC formulator received wrong problem class: {problem.problem_class}"
        )

    params = problem.params
    distance = int(params.get("distance", DEFAULT_DISTANCE))
    noise_rate = float(params.get("noise_rate", DEFAULT_NOISE_RATE))
    shots = int(params.get("shots", DEFAULT_SHOTS))
    rounds = params.get("rounds", DEFAULT_ROUNDS)
    if rounds is not None:
        rounds = int(rounds)
    basis = str(params.get("basis", DEFAULT_BASIS)).upper()
    rotation = str(params.get("rotation", DEFAULT_ROTATION)).upper()

    syndrome = _generate_syndromes(distance, noise_rate, shots, rounds, basis, rotation)

    payload = {
        "problem_type": "qec_syndrome",
        "syndrome": syndrome,
        "config": {
            "distance": distance,
            "noise_rate": noise_rate,
            "shots": shots,
            "rounds": syndrome["n_rounds"],
            "basis": basis,
            "rotation": rotation,
        },
    }

    return BackendInput(problem=problem, payload=payload)
