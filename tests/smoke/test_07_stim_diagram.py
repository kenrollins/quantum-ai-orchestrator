"""Phase-0 viz render 1: Stim's Circuit.diagram() emits an SVG for a small
surface-code circuit. The result lands in runs/smoke/<UTC>/07_stim_circuit.svg
so the journal can reference an actual artifact.
"""

from __future__ import annotations

import pytest
import stim


@pytest.mark.viz
def test_stim_diagram_svg(out_dir):
    circuit = stim.Circuit.generated(
        "surface_code:rotated_memory_x", distance=3, rounds=1,
        before_measure_flip_probability=1e-3,
    )
    diagram = circuit.diagram("timeline-svg")
    svg_text = str(diagram)

    out_path = out_dir / "07_stim_circuit.svg"
    out_path.write_text(svg_text)

    assert svg_text.lstrip().startswith("<svg") or "<svg" in svg_text[:200], (
        f"expected SVG, got: {svg_text[:200]!r}"
    )
    assert len(svg_text) > 500, "SVG suspiciously small"
