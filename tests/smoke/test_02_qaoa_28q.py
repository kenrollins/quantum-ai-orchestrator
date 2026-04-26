"""Phase-0 numerical gate 2: 28-qubit QAOA via cuStateVec single GPU < 60s.

28 qubits ≈ 2^28 complex amplitudes ≈ 4 GB statevector — fits one RTX 6000 Ada
(48 GB) comfortably. We use the same `nvidia` cuStateVec target as gate 1.

Two-GPU pooling (`nvidia-mgpu`) is unavailable on RTX 6000 Ada (no NVLink),
which is why this gate is constrained to single-GPU. See ADR-0002.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap

import pytest

SNIPPET = textwrap.dedent("""
    import json, time
    import cudaq

    cudaq.set_target("nvidia")  # single-GPU cuStateVec

    n = 28
    raw = []
    for i in range(n):
        for d in (1, 5, 11):
            j = (i + d) % n
            if i != j:
                raw.append((min(i, j), max(i, j)))
    edges = sorted(set(raw))
    edges_a = [int(a) for a, _ in edges]
    edges_b = [int(b) for _, b in edges]
    n_edges = len(edges)

    @cudaq.kernel
    def qaoa(gamma: float, beta: float, n_qubits: int, n_edges: int,
             edges_a: list[int], edges_b: list[int]):
        q = cudaq.qvector(n_qubits)
        for i in range(n_qubits):
            h(q[i])
        for k in range(n_edges):
            a = edges_a[k]
            b = edges_b[k]
            x.ctrl(q[a], q[b])
            rz(2.0 * gamma, q[b])
            x.ctrl(q[a], q[b])
        for i in range(n_qubits):
            rx(2.0 * beta, q[i])

    # Warm-up — keeps wall_time fair across backends.
    cudaq.sample(qaoa, 0.42, 0.31, n, n_edges, edges_a, edges_b, shots_count=64)

    t0 = time.perf_counter()
    res = cudaq.sample(qaoa, 0.42, 0.31, n, n_edges, edges_a, edges_b, shots_count=1024)
    dt = time.perf_counter() - t0

    counts = {k: v for k, v in res.items()}
    print(json.dumps({"qubits": n, "edges": n_edges, "wall_seconds": dt,
                      "unique_outcomes": len(counts)}))
""")


@pytest.mark.numerical
@pytest.mark.needs_gpu
@pytest.mark.needs_cudaq
def test_qaoa_28q_under_60s(cudaq_image, out_dir, write_artifact):
    if shutil.which("docker") is None:
        pytest.skip("docker not on PATH")

    snippet_path = out_dir / "02_qaoa_28q_snippet.py"
    snippet_path.write_text(SNIPPET)

    cmd = [
        "docker", "run", "--rm", "--gpus", "all",
        "-v", f"{out_dir}:/work:ro",
        "--entrypoint", "/usr/bin/python3",
        cudaq_image, "/work/02_qaoa_28q_snippet.py",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    write_artifact("02_qaoa_28q.stdout.txt", proc.stdout)
    write_artifact("02_qaoa_28q.stderr.txt", proc.stderr)
    assert proc.returncode == 0, proc.stderr

    last_json = [l for l in proc.stdout.strip().splitlines() if l.startswith("{")][-1]
    payload = json.loads(last_json)
    write_artifact("02_qaoa_28q.json", payload)

    assert payload["qubits"] == 28
    assert payload["wall_seconds"] < 60.0, f"wall={payload['wall_seconds']:.2f}s exceeded 60s gate"
