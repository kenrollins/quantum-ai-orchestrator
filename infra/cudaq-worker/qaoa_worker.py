"""CUDA-Q QAOA worker.

Runs inside the `nvcr.io/nvidia/quantum/cuda-quantum:cu12-0.9.1` container.

Protocol:
  stdin:  JSON {"qubo": [[...]], "num_layers": 4, "num_shots": 1000, "seed": 42}
  stdout: JSON {"sample": [...], "objective": float, "energy": float, "wall_time_ms": int}
  stderr: human-readable progress + diagnostics

The host-side backend (orchestrator/quantum/backends/cudaq_qaoa.py) shells
out into a container with `--gpus device=<lane>` to pin each invocation
to a specific GPU.

Notes:
- Maps QUBO -> Ising spin form (s_i in {-1, +1}) for QAOA's typical
  spin-Hamiltonian formulation, then maps back to bits for the sample.
- COBYLA classical optimizer (cudaq.optimizers.COBYLA), maxeval=100.
- num_qubits = QUBO size; circuit has 2*num_layers gamma/beta params.
- Temperature/depth tuning is conservative — we want a working
  baseline, not a tuned demo. Hyperparameters can move into config later.
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from typing import Any

import numpy as np


def _qubo_to_ising(Q: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Convert a QUBO (binary x in {0,1}) to Ising form (spin s in {-1,+1}).

    Substitution x = (1 - s) / 2 gives:
        x^T Q x = const + h^T s + s^T J s   (J upper triangular)

    Returns (h, J, const).
    """
    n = Q.shape[0]
    Q_sym = (Q + Q.T) / 2.0  # symmetrize
    h = np.zeros(n)
    J = np.zeros((n, n))
    const = 0.0

    # x_i = (1 - s_i) / 2  =>  x_i x_j = (1 - s_i)(1 - s_j) / 4
    # x_i x_j = 1/4 - s_i/4 - s_j/4 + s_i s_j / 4
    for i in range(n):
        for j in range(n):
            qij = Q_sym[i, j]
            if qij == 0.0:
                continue
            const += qij / 4.0
            h[i] -= qij / 4.0
            h[j] -= qij / 4.0
            if i != j:
                J[min(i, j), max(i, j)] += qij / 4.0
            else:
                # diagonal: x_i^2 = x_i (binary), so s_i^2 = 1 contributes only to const
                # Already counted in const.
                pass

    return h, J, const


def _build_cost_hamiltonian(h: np.ndarray, J: np.ndarray):
    """Build a CUDA-Q SpinOperator for the Ising cost Hamiltonian."""
    from cudaq import spin

    n = len(h)
    H = 0 * spin.i(0)
    for i in range(n):
        if h[i] != 0:
            H += float(h[i]) * spin.z(i)
    for i in range(n):
        for j in range(i + 1, n):
            if J[i, j] != 0:
                H += float(J[i, j]) * spin.z(i) * spin.z(j)
    return H


def _build_qaoa(num_qubits: int, num_layers: int, h: np.ndarray, J: np.ndarray):
    """Build QAOA via the cudaq builder API (works inside this container version)."""
    import cudaq

    kernel, params = cudaq.make_kernel(list)
    qubits = kernel.qalloc(num_qubits)

    # Initial uniform superposition
    kernel.h(qubits)

    for layer in range(num_layers):
        gamma_idx = layer
        beta_idx = num_layers + layer

        # Cost layer: e^{-i gamma H_cost}
        # h_i Z_i  -> Rz(2*gamma*h_i) on qubit i
        for i in range(num_qubits):
            if h[i] != 0:
                kernel.rz(2.0 * float(h[i]) * params[gamma_idx], qubits[i])
        # J_ij Z_i Z_j -> CX i,j ; Rz(2*gamma*J_ij) j ; CX i,j
        for i in range(num_qubits):
            for j in range(i + 1, num_qubits):
                if J[i, j] != 0:
                    kernel.cx(qubits[i], qubits[j])
                    kernel.rz(2.0 * float(J[i, j]) * params[gamma_idx], qubits[j])
                    kernel.cx(qubits[i], qubits[j])

        # Mixer layer: e^{-i beta H_mixer}, H_mixer = sum_i X_i
        # -> Rx(2*beta) on every qubit
        for i in range(num_qubits):
            kernel.rx(2.0 * params[beta_idx], qubits[i])

    return kernel


def run_qaoa(
    qubo: np.ndarray,
    num_layers: int,
    num_shots: int,
    seed: int,
) -> dict[str, Any]:
    import cudaq

    # Pick a GPU target. Default cudaq target inside container is fine.
    cudaq.set_target("nvidia")

    h, J, const = _qubo_to_ising(qubo)
    n = qubo.shape[0]
    num_params = 2 * num_layers

    cost_H = _build_cost_hamiltonian(h, J)
    kernel = _build_qaoa(n, num_layers, h, J)

    # Optimizer
    optimizer = cudaq.optimizers.COBYLA()
    optimizer.max_iterations = 80
    np.random.seed(seed)
    init = (np.random.uniform(0, np.pi, num_params)).tolist()
    optimizer.initial_parameters = init

    # Energy callback for VQE
    energy_value, optimal_params = cudaq.vqe(
        kernel=kernel,
        spin_operator=cost_H,
        optimizer=optimizer,
        parameter_count=num_params,
    )

    # Sample at optimal params to get the best bitstring
    counts = cudaq.sample(kernel, optimal_params, shots_count=num_shots)
    counts_dict: dict[str, int] = {bs: int(c) for bs, c in counts.items()}

    if not counts_dict:
        raise RuntimeError("QAOA produced no samples")
    best_bitstring = counts.most_probable()
    sample_bits = np.array([int(c) for c in best_bitstring], dtype=np.uint8)

    # Compute QUBO objective directly
    objective = float(sample_bits @ qubo @ sample_bits)

    return {
        "sample": sample_bits.tolist(),
        "objective": objective,
        "energy": float(energy_value) + float(const),
        "qaoa_energy": float(energy_value),
        "ising_const": float(const),
        "num_layers": num_layers,
        "num_shots": num_shots,
        "top_counts": dict(sorted(counts_dict.items(), key=lambda kv: -kv[1])[:5]),
    }


def main() -> int:
    raw = sys.stdin.read()
    try:
        job = json.loads(raw)
    except Exception as e:
        print(json.dumps({"success": False, "error": f"Bad input JSON: {e}"}))
        return 2

    qubo_list = job.get("qubo")
    if qubo_list is None:
        print(json.dumps({"success": False, "error": "Missing 'qubo' in input"}))
        return 2

    qubo = np.asarray(qubo_list, dtype=float)
    num_layers = int(job.get("num_layers", 3))
    num_shots = int(job.get("num_shots", 1000))
    seed = int(job.get("seed", 42))

    start = time.perf_counter()
    try:
        result = run_qaoa(qubo, num_layers, num_shots, seed)
        wall_time_ms = int((time.perf_counter() - start) * 1000)
        result["success"] = True
        result["wall_time_ms"] = wall_time_ms
        print(json.dumps(result))
        return 0
    except Exception as e:
        wall_time_ms = int((time.perf_counter() - start) * 1000)
        tb = traceback.format_exc()
        print(
            json.dumps(
                {
                    "success": False,
                    "error": str(e),
                    "traceback": tb,
                    "wall_time_ms": wall_time_ms,
                }
            )
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
