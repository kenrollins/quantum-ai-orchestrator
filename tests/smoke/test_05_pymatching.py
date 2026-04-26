"""Phase-0 numerical gate 5: PyMatching decodes the gate-3 syndrome stream
in < 200 ms (per-shot or batch — we measure batch and report per-shot).

This is the classical baseline that NVIDIA Ising must beat in the federal demo.
"""

from __future__ import annotations

import time

import numpy as np
import pymatching
import pytest
import stim


@pytest.mark.numerical
def test_pymatching_decode_under_200ms(out_dir, write_artifact):
    syndrome_npz = out_dir / "03_stim_d5_syndromes.npz"
    if not syndrome_npz.exists():
        pytest.skip("gate 3 (stim syndrome) hasn't run; this gate consumes its output")

    data = np.load(syndrome_npz)
    detection_events = data["detection_events"]
    observable_flips = data["observable_flips"]

    dem_path = out_dir / "03_stim_d5.dem"
    dem = stim.DetectorErrorModel(dem_path.read_text())
    matching = pymatching.Matching.from_detector_error_model(dem)

    t0 = time.perf_counter()
    predictions = matching.decode_batch(detection_events)
    dt_s = time.perf_counter() - t0

    if observable_flips.ndim == 1:
        observable_flips = observable_flips.reshape(-1, 1)
    if predictions.ndim == 1:
        predictions = predictions.reshape(-1, 1)

    n_shots = detection_events.shape[0]
    n_logical_errors = int(np.any(predictions != observable_flips, axis=1).sum())

    payload = {
        "shots": int(n_shots),
        "wall_seconds_total": dt_s,
        "wall_ms_per_shot": (dt_s * 1000) / n_shots,
        "logical_errors": n_logical_errors,
        "logical_error_rate": n_logical_errors / n_shots,
    }
    write_artifact("05_pymatching.json", payload)

    assert dt_s < 0.200, f"batch decode wall={dt_s*1000:.1f}ms exceeded 200ms gate"
