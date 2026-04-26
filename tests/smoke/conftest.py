"""Shared fixtures + markers for the Phase-0 smoke gate.

The gate is split per plan §3 into:
  * 6 numerical tests — `pytest -m numerical`
  * 5 visualization renders — `pytest -m viz`

`make smoke` runs both. Outputs (timings, SVG/PNG renders, JSON summaries)
land under runs/smoke/<UTC>/ so the journal can reference concrete artifacts.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS_ROOT = REPO_ROOT / "runs" / "smoke"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "numerical: Phase-0 numerical gate")
    config.addinivalue_line("markers", "viz: Phase-0 visualization render")
    config.addinivalue_line("markers", "needs_gpu: requires at least one CUDA GPU")
    config.addinivalue_line("markers", "needs_cudaq: requires the CUDA-Q container image")
    config.addinivalue_line("markers", "needs_ising_weights: requires NVIDIA Ising decoder weights")


@pytest.fixture(scope="session")
def out_dir() -> Path:
    """Per-session output directory under runs/smoke/<UTC>/."""
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    d = RUNS_ROOT / stamp
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture(scope="session")
def cudaq_image() -> str:
    return os.environ.get(
        "CUDAQ_IMAGE", "nvcr.io/nvidia/quantum/cuda-quantum:cu12-0.9.1"
    )


@pytest.fixture(scope="session")
def docker_available() -> bool:
    return shutil.which("docker") is not None


@pytest.fixture
def write_artifact(out_dir: Path):
    """Returns a callable: write_artifact(name, payload) -> Path."""

    def _write(name: str, payload: bytes | str | dict) -> Path:
        dest = out_dir / name
        if isinstance(payload, dict):
            dest.write_text(json.dumps(payload, indent=2, default=str))
        elif isinstance(payload, bytes):
            dest.write_bytes(payload)
        else:
            dest.write_text(payload)
        return dest

    return _write
