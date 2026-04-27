"""CUDA-Q QAOA worker.

Runs inside the `nvcr.io/nvidia/quantum/cuda-quantum:cu12-0.9.1` container.

Protocol:
  stdin:  JSON {"qubo": [[...]], "num_layers": 5, "num_shots": 2000,
                "num_restarts": 4, "max_iterations": 150, "seed": 42}
  stdout: JSON {"sample": [...], "objective": float, "energy": float,
                "best_restart": int, "wall_time_ms": int, ...}
  stderr: human-readable progress + diagnostics

Backend selection by problem size:
  n <= 24 qubits  -> nvidia          (full statevector on GPU; exact, fast)
  n <= 64 qubits  -> tensornet-mps   (matrix product states; approximate but
                                      handles structured QUBOs at moderate
                                      QAOA depth)
  n >  64 qubits  -> graceful refuse (return success=False with a clear
                                      out-of-scope message; CUDA-Q QAOA on
                                      consumer GPUs caps here for now)

QAOA being QAOA: even with the right simulator, COBYLA from a single random
start regularly lands in a bad local minimum. The worker tries several random
restarts in series and keeps the lowest-energy parameters before sampling.
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


def _select_target(n: int) -> str:
    """Pick a CUDA-Q simulator backend by problem size."""
    if n <= 24:
        return "nvidia"          # full statevector on GPU
    if n <= 64:
        return "tensornet-mps"   # MPS approximation, handles structured QUBOs
    return ""                    # too big — caller should refuse


def run_qaoa(
    qubo: np.ndarray,
    num_layers: int,
    num_shots: int,
    num_restarts: int,
    max_iterations: int,
    seed: int,
) -> dict[str, Any]:
    import cudaq

    h, J, const = _qubo_to_ising(qubo)
    n = qubo.shape[0]
    num_params = 2 * num_layers

    # Normalize Hamiltonian coefficients so the Rz angles aren't huge.
    # Without this, |h|+|J| can be in the hundreds, which means a small
    # parameter step turns into a large rotation and COBYLA bounces around.
    # The expectation value scales linearly with `scale` so we just track it
    # and multiply back when we report the absolute energy.
    scale = float(max(np.abs(h).max(), np.abs(J).max(), 1.0))
    h_n = h / scale
    J_n = J / scale

    target = _select_target(n)
    if not target:
        raise RuntimeError(
            f"QAOA on consumer GPU caps at 64 qubits (statevector ≤24, MPS ≤64). "
            f"This problem has {n} variables. Use neal or classical_ortools."
        )
    cudaq.set_target(target)

    cost_H = _build_cost_hamiltonian(h_n, J_n)
    kernel = _build_qaoa(n, num_layers, h_n, J_n)

    # Multi-restart: COBYLA from a single point gets stuck in local minima
    # routinely on small QAOA. We try `num_restarts` independent initial
    # parameter sets and keep the lowest-energy result. The first restart
    # uses a linear ramp (gamma_l = (l+1)/L * pi/2, beta_l = (1 - (l+1)/L) * pi/4)
    # which is the standard QAOA warm-start; the rest are random uniform.
    rng = np.random.default_rng(seed)
    best_energy_norm = float("inf")
    best_params: list[float] | None = None
    restart_log: list[dict[str, Any]] = []
    for r in range(max(1, num_restarts)):
        if r == 0:
            # Linear-ramp warm-start: gammas grow from 0 to π/2, betas
            # shrink from π/4 toward 0 — empirically a strong starting
            # point for QAOA on max-cut-style cost Hamiltonians.
            gammas = [(l + 1) / num_layers * (np.pi / 2) for l in range(num_layers)]
            betas = [(1 - (l + 1) / num_layers) * (np.pi / 4) for l in range(num_layers)]
            init = gammas + betas
        else:
            init = rng.uniform(0, np.pi, num_params).tolist()
        optimizer = cudaq.optimizers.COBYLA()
        optimizer.max_iterations = int(max_iterations)
        optimizer.initial_parameters = init
        try:
            energy_value, optimal_params = cudaq.vqe(
                kernel=kernel,
                spin_operator=cost_H,
                optimizer=optimizer,
                parameter_count=num_params,
            )
        except Exception as e:
            restart_log.append({"restart": r, "error": str(e)[:100]})
            continue
        restart_log.append({
            "restart": r,
            "init": "ramp" if r == 0 else "random",
            "energy_norm": float(energy_value),
        })
        if energy_value < best_energy_norm:
            best_energy_norm = float(energy_value)
            best_params = list(optimal_params)

    if best_params is None:
        raise RuntimeError(
            "QAOA optimization failed on every restart. "
            f"Restart log: {restart_log}"
        )

    # Sample at the best params we found across restarts
    counts = cudaq.sample(kernel, best_params, shots_count=num_shots)
    counts_dict: dict[str, int] = {bs: int(c) for bs, c in counts.items()}

    if not counts_dict:
        raise RuntimeError("QAOA produced no samples after optimization")

    # Pick the *minimum-cost* feasible bitstring among the most-frequent
    # samples — most_probable() can pick an infeasible local mode in
    # underweighted-penalty regimes. We rank top-K by direct QUBO cost.
    top_k = min(20, len(counts_dict))
    top_pairs = sorted(counts_dict.items(), key=lambda kv: -kv[1])[:top_k]
    best_bitstring, _best_count = top_pairs[0]
    best_obj = float("inf")
    for bs, _ct in top_pairs:
        bits = np.array([int(c) for c in bs], dtype=np.uint8)
        obj = float(bits @ qubo @ bits)
        if obj < best_obj:
            best_obj = obj
            best_bitstring = bs

    sample_bits = np.array([int(c) for c in best_bitstring], dtype=np.uint8)
    objective = float(sample_bits @ qubo @ sample_bits)

    # Convert the normalized energy back to absolute Ising units
    abs_energy = best_energy_norm * scale + float(const)
    return {
        "sample": sample_bits.tolist(),
        "objective": objective,
        "energy": float(abs_energy),
        "qaoa_energy_normalized": float(best_energy_norm),
        "scale": float(scale),
        "ising_const": float(const),
        "num_qubits": n,
        "num_layers": num_layers,
        "num_shots": num_shots,
        "num_restarts": num_restarts,
        "target": target,
        "restart_log": restart_log,
        "top_counts": dict(top_pairs[:5]),
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
    num_layers = int(job.get("num_layers", 5))
    num_shots = int(job.get("num_shots", 2000))
    num_restarts = int(job.get("num_restarts", 4))
    max_iterations = int(job.get("max_iterations", 150))
    seed = int(job.get("seed", 42))

    start = time.perf_counter()
    try:
        result = run_qaoa(
            qubo,
            num_layers=num_layers,
            num_shots=num_shots,
            num_restarts=num_restarts,
            max_iterations=max_iterations,
            seed=seed,
        )
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
