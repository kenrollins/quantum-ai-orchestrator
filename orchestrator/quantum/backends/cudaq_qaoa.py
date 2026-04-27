"""CUDA-Q QAOA backend.

CUDA-Q lives in `nvcr.io/nvidia/quantum/cuda-quantum:cu12-0.9.1` per ADR-0003.
We shell out via `docker run --rm --gpus device=<lane>` for each invocation,
mounting `infra/cudaq-worker/` so the container can execute `qaoa_worker.py`.

Cold start is ~2-3s per call (container spin-up). For Phase 1 that's
acceptable; Phase 2 can switch to a long-lived per-lane container with
a thin RPC interface if startup cost becomes an issue.

Worker contract (see infra/cudaq-worker/qaoa_worker.py):
  stdin:  {"qubo": [[...]], "num_layers": int, "num_shots": int, "seed": int}
  stdout: {"sample": [...], "objective": float, "wall_time_ms": int, ...}
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

import numpy as np

from orchestrator.pipeline.types import BackendInput, Solution

from .base import failed_solution, timed

logger = logging.getLogger(__name__)

BACKEND_NAME = "cudaq_qaoa"
CONTAINER_IMAGE = "nvcr.io/nvidia/quantum/cuda-quantum:cu12-0.9.1"
WORKER_DIR = Path(__file__).resolve().parents[3] / "infra" / "cudaq-worker"
WORKER_SCRIPT_IN_CONTAINER = "/work/qaoa_worker.py"

DEFAULT_NUM_LAYERS = 3
DEFAULT_NUM_SHOTS = 1000
DEFAULT_TIMEOUT_S = 120


def _build_docker_cmd(gpu_lane: int | None) -> list[str]:
    """Build the docker command, pinning to a specific GPU when possible."""
    gpus_arg = f"device={gpu_lane}" if gpu_lane is not None else "all"
    return [
        "docker", "run", "--rm", "-i",
        "--gpus", gpus_arg,
        "--entrypoint", "/usr/bin/python",
        "-v", f"{WORKER_DIR}:/work",
        CONTAINER_IMAGE,
        WORKER_SCRIPT_IN_CONTAINER,
    ]


def run(
    backend_input: BackendInput,
    gpu_lane: int | None = None,
) -> Solution:
    """Solve a QUBO via CUDA-Q QAOA in the container.

    Args:
        backend_input: Must carry `qubo_matrix` and `metadata`.
        gpu_lane: Which GPU to pin the container to (0 or 1).
    """
    payload = backend_input.payload
    qubo_matrix = payload.get("qubo_matrix")
    metadata = payload.get("metadata", {})
    config = payload.get("config", {})

    if qubo_matrix is None:
        return failed_solution(BACKEND_NAME, "Missing qubo_matrix in payload")

    if not WORKER_DIR.exists():
        return failed_solution(
            BACKEND_NAME,
            f"Worker directory not found at {WORKER_DIR}",
        )

    job = {
        "qubo": np.asarray(qubo_matrix, dtype=float).tolist(),
        "num_layers": int(config.get("num_layers", DEFAULT_NUM_LAYERS)),
        "num_shots": int(config.get("num_shots", DEFAULT_NUM_SHOTS)),
        "seed": int(config.get("seed", 42)),
    }

    cmd = _build_docker_cmd(gpu_lane)
    logger.info(
        "cudaq_qaoa: docker run on gpu_lane=%s, num_layers=%d, num_shots=%d",
        gpu_lane,
        job["num_layers"],
        job["num_shots"],
    )

    with timed() as t:
        try:
            proc = subprocess.run(
                cmd,
                input=json.dumps(job).encode("utf-8"),
                capture_output=True,
                timeout=DEFAULT_TIMEOUT_S,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return failed_solution(
                BACKEND_NAME,
                f"Container timed out after {DEFAULT_TIMEOUT_S}s",
                wall_time_ms=t["wall_time_ms"],
            )
        except FileNotFoundError as e:
            return failed_solution(
                BACKEND_NAME,
                f"docker not found: {e}",
            )

    stdout = proc.stdout.decode("utf-8", errors="replace").strip()
    stderr = proc.stderr.decode("utf-8", errors="replace").strip()

    # Worker writes a single JSON line to stdout. Other lines (warnings, banner)
    # may be present; pick the last JSON line.
    json_line = None
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            json_line = line
            break

    if json_line is None:
        return failed_solution(
            BACKEND_NAME,
            f"No JSON output from worker. exit={proc.returncode} stderr={stderr[:500]}",
            wall_time_ms=t["wall_time_ms"],
        )

    try:
        result = json.loads(json_line)
    except json.JSONDecodeError as e:
        return failed_solution(
            BACKEND_NAME,
            f"Invalid JSON from worker: {e}; line={json_line[:200]}",
            wall_time_ms=t["wall_time_ms"],
        )

    if not result.get("success", False):
        return failed_solution(
            BACKEND_NAME,
            result.get("error", "Worker reported failure"),
            wall_time_ms=t["wall_time_ms"],
        )

    sample = np.asarray(result["sample"], dtype=np.uint8)

    # Decode assignment for convenience
    num_assets = metadata.get("num_assets", config.get("assets", 0))
    num_tasks = metadata.get("num_tasks", config.get("tasks", 0))
    assignment: dict[int, int] = {}
    for i in range(num_assets):
        for j in range(num_tasks):
            if sample[i * num_tasks + j] == 1 and j not in assignment:
                assignment[j] = i

    objective = result.get("objective")
    if objective is None and metadata.get("cost_matrix") is not None:
        cm = np.asarray(metadata["cost_matrix"])
        objective = float(sum(cm[i, j] for j, i in assignment.items()))

    logger.info(
        "cudaq_qaoa: gpu_lane=%s objective=%s qaoa_energy=%s container_ms=%d",
        gpu_lane,
        objective,
        result.get("qaoa_energy"),
        result.get("wall_time_ms"),
    )

    return Solution(
        backend_name=BACKEND_NAME,
        payload={
            "sample": sample,
            "assignment": assignment,
            "objective": objective,
            "energy": result.get("energy"),
            "qaoa_energy": result.get("qaoa_energy"),
            "metadata": metadata,
            "num_layers": job["num_layers"],
            "num_shots": job["num_shots"],
            "top_counts": result.get("top_counts", {}),
            "container_wall_time_ms": result.get("wall_time_ms"),
            "gpu_lane": gpu_lane,
            "solver": "cudaq_qaoa",
        },
        wall_time_ms=t["wall_time_ms"],
        success=True,
    )
