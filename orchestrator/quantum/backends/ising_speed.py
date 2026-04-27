"""NVIDIA Ising Decoder — Fast variant (Model 1, R=9).

Loads weights from `/data/models/nvidia-ising/fast/` and runs as a
predecoder-plus-PyMatching ensemble. Implementation lives in
`_ising_common.py`; this module is a thin wrapper that pins the
variant identity (model_id, weights path, label).

Phase 1 status: real GPU forward pass; residual built in 'syn_only' mode
(stabilizer-error channels only, no data-correction parity sums or
logical-frame XOR). The full ensemble that matches NVIDIA's published
LER reduction will land in a later round — see ADR-0011.
"""

from __future__ import annotations

from pathlib import Path

from orchestrator.pipeline.types import BackendInput, Solution

from ._ising_common import IsingVariant, run_predecoder_pipeline

BACKEND_NAME = "ising_speed"

VARIANT = IsingVariant(
    backend_name=BACKEND_NAME,
    model_id=1,
    weights_path=Path(
        "/data/models/nvidia-ising/fast/"
        "ising_decoder_surface_code_1_fast_r9_v1.0.77_fp16.safetensors"
    ),
    variant_label="fast",
)


def run(
    backend_input: BackendInput,
    gpu_lane: int | None = None,
) -> Solution:
    return run_predecoder_pipeline(VARIANT, backend_input, gpu_lane)
