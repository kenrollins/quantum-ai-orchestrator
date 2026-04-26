"""Phase-0 numerical gate 4: NVIDIA Ising Decoding predecoder forward pass < 50 ms.

The predecoder weights live at /data/models/nvidia-ising/ (out of repo, .gitignored).
The inference code lives in /data/models/nvidia-ising/Ising-Decoding/ (cloned from
GitHub NVIDIA/Ising-Decoding).

The predecoder is a 3D-CNN that takes syndrome volumes and produces soft information
for a downstream MWPM decoder (PyMatching). This test validates the forward pass only.

If the weights or inference repo aren't on disk yet (bootstrap_ising.sh hasn't run,
or the repo hasn't been cloned), we skip with a clear note.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest
import torch

WEIGHTS_DIR = Path("/data/models/nvidia-ising")
ISING_REPO = WEIGHTS_DIR / "Ising-Decoding"
FAST_WEIGHTS = WEIGHTS_DIR / "fast" / "ising_decoder_surface_code_1_fast_r9_v1.0.77_fp16.safetensors"


@pytest.mark.numerical
@pytest.mark.needs_gpu
@pytest.mark.needs_ising_weights
def test_ising_decode_under_50ms(out_dir, write_artifact):
    """Load the NVIDIA Ising predecoder and run a forward pass on synthetic input."""
    if not WEIGHTS_DIR.is_dir():
        pytest.skip(
            f"NVIDIA Ising weights directory not found at {WEIGHTS_DIR}. "
            "Run tools/bootstrap_ising.sh first."
        )
    if not FAST_WEIGHTS.exists():
        pytest.skip(
            f"Fast model weights not found at {FAST_WEIGHTS}. "
            "Run tools/bootstrap_ising.sh first."
        )
    if not ISING_REPO.is_dir():
        pytest.skip(
            f"Ising-Decoding repo not found at {ISING_REPO}. "
            "Clone https://github.com/NVIDIA/Ising-Decoding.git there."
        )
    if not torch.cuda.is_available():
        pytest.skip("CUDA not available")

    # Add the repo's code directory to sys.path
    code_path = str(ISING_REPO / "code")
    if code_path not in sys.path:
        sys.path.insert(0, code_path)

    from export.safetensors_utils import load_safetensors

    # Load the model
    device = "cuda:0"
    model, metadata = load_safetensors(str(FAST_WEIGHTS), device=device)
    model.eval()

    info = {
        "model_id": metadata.get("model_id"),
        "quant_format": metadata.get("quant_format"),
        "receptive_field": metadata.get("receptive_field"),
        "device": device,
    }

    # Create synthetic input matching model spec
    # Model 1 (fast): receptive_field=9, input shape (B, 4, T, D, D)
    # where T=n_rounds, D=distance. We use d=9, n_rounds=9 matching R.
    batch_size = 1
    in_channels = 4  # syndrome channels
    n_rounds = 9
    distance = 9
    x = torch.randn(batch_size, in_channels, n_rounds, distance, distance,
                    device=device, dtype=torch.float16)

    # Warmup
    with torch.no_grad():
        _ = model(x)
    torch.cuda.synchronize()

    # Timed forward pass
    t0 = time.perf_counter()
    with torch.no_grad():
        out = model(x)
    torch.cuda.synchronize()
    wall_ms = (time.perf_counter() - t0) * 1000

    info["wall_ms"] = wall_ms
    info["input_shape"] = list(x.shape)
    info["output_shape"] = list(out.shape)

    write_artifact("04_ising_decode.json", info)

    assert out.shape[0] == batch_size, f"batch mismatch: {out.shape}"
    assert out.shape[1] == 4, f"expected 4 output channels, got {out.shape[1]}"
    assert wall_ms < 50.0, f"Ising forward pass took {wall_ms:.2f}ms (gate: <50ms)"
