"""Backend base contract.

Every backend module exposes a `run` function with this signature:

    def run(backend_input: BackendInput, gpu_lane: int | None = None) -> Solution

Backends should:
- Time their own execution (wall_time_ms in the returned Solution)
- Catch their own exceptions and return Solution(success=False, error=str(e))
- Never raise — failure is data, not an error
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator, Protocol

from orchestrator.pipeline.types import BackendInput, Solution


class BackendRunner(Protocol):
    """Structural type for backend modules. Modules satisfy this implicitly."""

    def run(
        self,
        backend_input: BackendInput,
        gpu_lane: int | None = None,
    ) -> Solution:
        ...


@contextmanager
def timed() -> Iterator[dict[str, int]]:
    """Yield a dict that fills in `wall_time_ms` when the block exits."""
    start = time.perf_counter()
    out: dict[str, int] = {"wall_time_ms": 0}
    try:
        yield out
    finally:
        out["wall_time_ms"] = int((time.perf_counter() - start) * 1000)


def failed_solution(
    backend_name: str,
    error: str,
    wall_time_ms: int = 0,
) -> Solution:
    """Build a Solution that signals failure to the evaluator."""
    return Solution(
        backend_name=backend_name,
        payload={},
        wall_time_ms=wall_time_ms,
        success=False,
        error=error,
    )
