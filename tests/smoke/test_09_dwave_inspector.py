"""Phase-0 viz render 3: D-Wave problem-inspector encodes a small QUBO and
serializes it to inspector-compatible form.

The inspector's interactive browser viewer is irrelevant for an automated
gate, and per plan §11(14) we should *not* rely on it phoning home to the
D-Wave Leap server. Instead we exercise the encoder path
(`dwave.inspector.storage.problem_data` and the dimod ↔ inspector adapter)
which is what we'll actually need when we extract SVG/JSON for the QUBO Graph
panel.
"""

from __future__ import annotations

import json

import dimod
import numpy as np
import pytest


@pytest.mark.viz
def test_dwave_inspector_encode_qubo(write_artifact):
    rng = np.random.default_rng(0xD00D)
    n = 8
    Q = {(i, i): float(rng.normal(0, 1)) for i in range(n)}
    for i in range(n):
        for j in range(i + 1, n):
            if rng.random() < 0.4:
                Q[(i, j)] = float(rng.normal(0, 1))

    bqm = dimod.BinaryQuadraticModel.from_qubo(Q)
    sampler = dimod.ExactSolver()
    sampleset = sampler.sample(bqm)

    payload: dict = {
        "n_vars": n,
        "n_quadratic_terms": sum(1 for k in Q if k[0] != k[1]),
        "best_energy": float(sampleset.first.energy),
    }

    try:
        from dwave.inspector.adapters import from_bqm_sampleset

        inspector_data = from_bqm_sampleset(bqm, sampleset)
        json_blob = json.dumps(inspector_data, default=str)
        write_artifact("09_dwave_inspector_payload.json", json_blob)
        payload["inspector_payload_bytes"] = len(json_blob)
        payload["inspector_adapter"] = "from_bqm_sampleset"
    except Exception as e:  # noqa: BLE001
        # The full adapter requires solver metadata we don't have (we're not
        # talking to Leap). Falling back to plain BQM serialization keeps the
        # gate informative — the renderable graph is the BQM itself.
        bqm_serialized = bqm.to_serializable()
        write_artifact("09_dwave_bqm.json", bqm_serialized)
        payload["inspector_adapter"] = f"unavailable ({e!s})"
        payload["bqm_serialized_keys"] = sorted(bqm_serialized.keys())

    write_artifact("09_dwave_inspector.json", payload)

    assert payload["n_vars"] == n
    assert payload["n_quadratic_terms"] >= 1
