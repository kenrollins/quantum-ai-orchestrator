"""Phase-0 numerical gate 1: 12-qubit Max-Cut QAOA via CUDA-Q < 5s on one RTX 6000 Ada.

We run inside the cuda-quantum container with the GPU0 simulator target
(`nvidia` backend = single-GPU cuStateVec). The host venv intentionally does
not carry CUDA-Q (ADR-0003); the container is the runtime.
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

    cudaq.set_target("nvidia")  # cuStateVec, GPU 0

    n = 12
    # Random-ish max-cut graph (1-step + 4-step ring), flattened to parallel
    # int lists because cudaq.kernel only closes over int/bool/float/complex
    # lists.
    raw = [(i, (i + 1) % n) for i in range(n)] + [(i, (i + 4) % n) for i in range(n)]
    edges = sorted({tuple(sorted(e)) for e in raw})
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

    # Warm-up: discard the first run so JIT + lib-load don't pollute timing.
    cudaq.sample(qaoa, 0.5, 0.7, n, n_edges, edges_a, edges_b, shots_count=128)

    t0 = time.perf_counter()
    res = cudaq.sample(qaoa, 0.5, 0.7, n, n_edges, edges_a, edges_b, shots_count=4096)
    dt = time.perf_counter() - t0

    counts = {k: v for k, v in res.items()}
    assert len(counts) > 1, "expected nontrivial distribution"

    print(json.dumps({"qubits": n, "edges": n_edges, "wall_seconds": dt,
                      "unique_outcomes": len(counts)}))
""")


@pytest.mark.numerical
@pytest.mark.needs_gpu
@pytest.mark.needs_cudaq
def test_qaoa_12q_under_5s(cudaq_image, out_dir, write_artifact):
    if shutil.which("docker") is None:
        pytest.skip("docker not on PATH")

    # cudaq.kernel uses inspect.getsource(); python -c has no source file.
    # Stage the snippet on disk and bind-mount its parent into the container.
    snippet_path = out_dir / "01_qaoa_12q_snippet.py"
    snippet_path.write_text(SNIPPET)

    cmd = [
        "docker", "run", "--rm", "--gpus", "all",
        "-v", f"{out_dir}:/work:ro",
        "--entrypoint", "/usr/bin/python3",
        cudaq_image, "/work/01_qaoa_12q_snippet.py",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    write_artifact("01_qaoa_12q.stdout.txt", proc.stdout)
    write_artifact("01_qaoa_12q.stderr.txt", proc.stderr)
    assert proc.returncode == 0, proc.stderr

    last_json = [l for l in proc.stdout.strip().splitlines() if l.startswith("{")][-1]
    payload = json.loads(last_json)
    write_artifact("01_qaoa_12q.json", payload)

    assert payload["qubits"] == 12
    assert payload["wall_seconds"] < 5.0, f"wall={payload['wall_seconds']:.2f}s exceeded 5s gate"
