"""Phase-0 numerical gate 3: Stim emits a distance-5 surface-code syndrome stream
under depolarizing noise p=1e-3 in < 2s.

We generate the rotated-memory-X surface code at distance 5 with one round of
syndrome extraction, then sample 4096 shots. The syndrome stream + DEM are
written under runs/smoke/<UTC>/ for use by gates 4 (Ising decode) and 5
(PyMatching decode).
"""

from __future__ import annotations

import time

import numpy as np
import pytest
import stim


@pytest.mark.numerical
def test_stim_d5_syndrome_under_2s(out_dir, write_artifact):
    distance = 5
    rounds = 1
    p = 1e-3
    shots = 4096

    t0 = time.perf_counter()
    circuit = stim.Circuit.generated(
        "surface_code:rotated_memory_x",
        distance=distance,
        rounds=rounds,
        after_clifford_depolarization=p,
        after_reset_flip_probability=p,
        before_measure_flip_probability=p,
        before_round_data_depolarization=p,
    )
    sampler = circuit.compile_detector_sampler(seed=0xCAFE)
    detection_events, observable_flips = sampler.sample(shots, separate_observables=True)
    dt_s = time.perf_counter() - t0

    syndrome_path = out_dir / "03_stim_d5_syndromes.npz"
    np.savez_compressed(
        syndrome_path,
        detection_events=detection_events,
        observable_flips=observable_flips,
    )

    dem = circuit.detector_error_model(decompose_errors=True)
    (out_dir / "03_stim_d5.dem").write_text(str(dem))

    payload = {
        "distance": distance,
        "rounds": rounds,
        "p": p,
        "shots": shots,
        "wall_seconds": dt_s,
        "n_detectors": detection_events.shape[1],
        "n_observables": observable_flips.shape[1] if observable_flips.ndim > 1 else 1,
        "syndrome_path": str(syndrome_path),
    }
    write_artifact("03_stim_d5.json", payload)

    assert dt_s < 2.0, f"wall={dt_s:.2f}s exceeded 2s gate"
    assert detection_events.shape == (shots, payload["n_detectors"])
