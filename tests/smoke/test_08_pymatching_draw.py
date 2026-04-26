"""Phase-0 viz render 2: PyMatching's `Matching.draw()` produces a matching-graph
visualization. PyMatching's draw() uses matplotlib + networkx — we render to PNG
and write under runs/smoke/<UTC>/.
"""

from __future__ import annotations

import pytest

# Headless matplotlib backend before the lib pulls it in.
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pymatching  # noqa: E402
import stim  # noqa: E402


@pytest.mark.viz
def test_pymatching_draw_png(out_dir):
    circuit = stim.Circuit.generated(
        "surface_code:rotated_memory_x", distance=3, rounds=1,
        after_clifford_depolarization=1e-3,
        before_measure_flip_probability=1e-3,
    )
    dem = circuit.detector_error_model(decompose_errors=True)
    matching = pymatching.Matching.from_detector_error_model(dem)

    fig = plt.figure(figsize=(8, 6))
    matching.draw()
    out_path = out_dir / "08_pymatching_draw.png"
    plt.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)

    assert out_path.exists()
    size = out_path.stat().st_size
    assert size > 5000, f"PNG suspiciously small ({size} bytes)"
