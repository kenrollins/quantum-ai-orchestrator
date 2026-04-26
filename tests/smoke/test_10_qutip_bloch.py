"""Phase-0 viz render 4: QuTiP renders a Bloch sphere with a few state vectors
to PNG. This is the server-side state-snapshot pathway plan §8 calls out for
the Quantum Visualizer panel.
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402
import qutip  # noqa: E402


@pytest.mark.viz
def test_qutip_bloch_png(out_dir):
    fig = plt.figure(figsize=(6, 6))
    bloch = qutip.Bloch(fig=fig)

    psi_plus = (qutip.basis(2, 0) + qutip.basis(2, 1)).unit()
    psi_minus = (qutip.basis(2, 0) - qutip.basis(2, 1)).unit()
    psi_phase = (qutip.basis(2, 0) + 1j * qutip.basis(2, 1)).unit()
    bloch.add_states([psi_plus, psi_minus, psi_phase])

    points = []
    for theta in np.linspace(0, np.pi, 12):
        phi = theta * 2.0
        points.append([np.sin(theta) * np.cos(phi),
                       np.sin(theta) * np.sin(phi),
                       np.cos(theta)])
    bloch.add_points(np.array(points).T)

    bloch.render()
    out_path = out_dir / "10_qutip_bloch.png"
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)

    size = out_path.stat().st_size
    assert size > 8000, f"Bloch PNG suspiciously small ({size} bytes)"
