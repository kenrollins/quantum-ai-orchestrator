"""NVIDIA Ising Decoder — Accurate variant (Model 4, R=13).

Loads weights from `/data/models/nvidia-ising/accurate/` and runs as a
predecoder-plus-PyMatching ensemble. Same Phase 1 caveat as ising_speed
about syn_only residual mode.
"""

from __future__ import annotations

from pathlib import Path

from orchestrator.pipeline.types import BackendInput, Solution

from ._ising_common import IsingVariant, run_predecoder_pipeline

BACKEND_NAME = "ising_accuracy"

VARIANT = IsingVariant(
    backend_name=BACKEND_NAME,
    model_id=4,
    weights_path=Path(
        "/data/models/nvidia-ising/accurate/"
        "ising_decoder_surface_code_1_accurate_r13_v1.0.86_fp16.safetensors"
    ),
    variant_label="accurate",
)


def run(
    backend_input: BackendInput,
    gpu_lane: int | None = None,
) -> Solution:
    return run_predecoder_pipeline(VARIANT, backend_input, gpu_lane)
