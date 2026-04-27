"""Dispatcher: Pick backends for each problem.

Reads config/backends.yaml and optionally consults the Postgres lessons
table for learned preferences. Returns one or more BackendChoices per input.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from .types import (
    BackendChoice,
    BackendClass,
    BackendConfig,
    BackendInput,
    Lesson,
    ProblemClass,
)

logger = logging.getLogger(__name__)

# Paths
CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
BACKENDS_CONFIG = CONFIG_DIR / "backends.yaml"

# GPU lane assignment state (simple round-robin for now)
_next_gpu_lane = 0


def _load_backend_registry() -> list[BackendConfig]:
    """Load backend configurations from YAML."""
    if not BACKENDS_CONFIG.exists():
        raise FileNotFoundError(f"Backend config not found: {BACKENDS_CONFIG}")

    with open(BACKENDS_CONFIG) as f:
        data = yaml.safe_load(f)

    backends = []
    for entry in data.get("backends", []):
        backends.append(
            BackendConfig(
                name=entry["name"],
                backend_class=BackendClass(entry["class"]),
                library=entry.get("library", ""),
                applicable_problem_classes=[
                    ProblemClass(pc) for pc in entry.get("applicable_problem_classes", [])
                ],
                gpu_required=entry.get("gpu_required", False),
                gpu_lane=entry.get("gpu_lane"),
                footprint_gb=entry.get("footprint_gb", 0),
                latency_target_ms=entry.get("latency_target_ms", 60000),
                phase=entry.get("phase", 1),
            )
        )

    return backends


# Cache the registry
_backend_registry: list[BackendConfig] | None = None


def get_backend_registry() -> list[BackendConfig]:
    """Get the backend registry, loading from disk if needed."""
    global _backend_registry
    if _backend_registry is None:
        _backend_registry = _load_backend_registry()
    return _backend_registry


def get_backends_for_problem_class(
    problem_class: ProblemClass,
    phase: int = 1,
) -> list[BackendConfig]:
    """Get all backends applicable to a problem class.

    Args:
        problem_class: The problem class to match.
        phase: Maximum phase to include (default: 1).

    Returns:
        List of applicable BackendConfigs.
    """
    registry = get_backend_registry()
    return [
        b
        for b in registry
        if problem_class in b.applicable_problem_classes and b.phase <= phase
    ]


def _assign_gpu_lane(backend: BackendConfig) -> int | None:
    """Assign a GPU lane to a backend that requires one.

    Simple round-robin between GPU 0 and GPU 1.
    """
    global _next_gpu_lane

    if not backend.gpu_required:
        return None

    lane = _next_gpu_lane
    _next_gpu_lane = (_next_gpu_lane + 1) % 2
    return lane


async def get_learned_preference(
    problem_class: ProblemClass,  # noqa: ARG001
    size_bucket: str,  # noqa: ARG001
) -> Lesson | None:
    """Query Postgres for a learned preference.

    Returns the currently-valid lesson for this problem class and size bucket,
    or None if no preference has been learned.
    """
    # TODO: Implement Postgres query once storage module is ready
    # For Phase 1, we return None (no learned preferences yet)
    _ = (problem_class, size_bucket)  # Will be used when Postgres is connected
    return None


async def dispatch(
    backend_input: BackendInput,
    top_k: int = 3,
    phase: int = 1,
) -> list[BackendChoice]:
    """Pick backends to run for a given input.

    Strategy:
    1. Get all applicable backends for the problem class
    2. Check for learned preferences in Postgres
    3. If preferred backend exists, put it first
    4. Return top_k backends

    Args:
        backend_input: The formulated input to dispatch.
        top_k: Maximum number of backends to return.
        phase: Maximum phase to include.

    Returns:
        List of BackendChoices with assigned GPU lanes.
    """
    problem = backend_input.problem
    problem_class = problem.problem_class
    size_bucket = problem.size_bucket

    logger.info(
        "Dispatching problem_id=%s class=%s bucket=%s",
        problem.problem_id,
        problem_class.value,
        size_bucket,
    )

    # Get applicable backends
    applicable = get_backends_for_problem_class(problem_class, phase)
    if not applicable:
        raise ValueError(f"No backends available for {problem_class} at phase {phase}")

    # Check for learned preference
    preference = await get_learned_preference(problem_class, size_bucket)

    # Sort: preferred first, then by name for determinism
    def sort_key(b: BackendConfig) -> tuple[int, str]:
        is_preferred = preference is not None and b.name == preference.preferred_backend
        return (0 if is_preferred else 1, b.name)

    sorted_backends = sorted(applicable, key=sort_key)

    # Take top_k and assign GPU lanes
    choices = []
    for backend in sorted_backends[:top_k]:
        lane = _assign_gpu_lane(backend)
        choices.append(BackendChoice(backend=backend, gpu_lane=lane))
        logger.debug(
            "Dispatching to %s (gpu_lane=%s)",
            backend.name,
            lane,
        )

    return choices


def dispatch_sync(
    backend_input: BackendInput,
    top_k: int = 3,
    phase: int = 1,
) -> list[BackendChoice]:
    """Synchronous wrapper for dispatch()."""
    import asyncio

    return asyncio.run(dispatch(backend_input, top_k, phase))
