"""Shared infrastructure for the NVIDIA Ising predecoder backends.

Both `ising_speed` (Model 1, R=9) and `ising_accuracy` (Model 4, R=13)
use the same PreDecoderModelMemory_v1 architecture, just with different
filter stacks and pretrained weights. This module owns:

- sys.path injection for NVIDIA's `Ising-Decoding/code` so we can import
  their `model.predecoder.PreDecoderModelMemory_v1` and the surface-code
  data-mapping helpers
- Lazy weight loading (cached after first call per process)
- Forward pass on the GPU lane assigned by the dispatcher
- Residual-syndrome construction (currently in 'syn_only' mode — uses the
  predecoder's stabilizer-error channels but not its data-error channels.
  This is a documented simplification; the full ensemble would also
  contribute parity sums S_X/S_Z and a logical-frame XOR pre_L. See
  ADR-0011 for the staged plan to upgrade this.)
- PyMatching decode of the residual

Result is a Solution with the same `predictions`/`observable_flips` shape
as the PyMatching baseline backend, so the QEC evaluator scores all three
QEC backends identically and the race is on the same data and metric.
"""

from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from types import SimpleNamespace

import numpy as np
import torch

from orchestrator.pipeline.types import BackendInput, Solution

from .base import failed_solution

logger = logging.getLogger(__name__)

NVIDIA_ISING_CODE_PATH = Path("/data/models/nvidia-ising/Ising-Decoding/code")


def _ensure_nvidia_path() -> None:
    p = str(NVIDIA_ISING_CODE_PATH)
    if not NVIDIA_ISING_CODE_PATH.exists():
        raise FileNotFoundError(
            f"NVIDIA Ising-Decoding code not found at {NVIDIA_ISING_CODE_PATH}"
        )
    if p not in sys.path:
        sys.path.insert(0, p)


@dataclass(frozen=True)
class IsingVariant:
    """Static info for a single Ising decoder variant."""

    backend_name: str
    model_id: int          # 1 = Fast (R=9), 4 = Accurate (R=13)
    weights_path: Path
    variant_label: str     # "fast" or "accurate"


# Cache: (variant.backend_name, distance, n_rounds, gpu_lane) -> loaded model
_MODEL_CACHE: dict[tuple[str, int, int, int], torch.nn.Module] = {}
_MODEL_CACHE_LOCK = Lock()


def _build_model_cfg(distance: int, n_rounds: int, model_id: int):
    _ensure_nvidia_path()
    from model.registry import get_model_spec  # type: ignore

    spec = get_model_spec(model_id)
    return SimpleNamespace(
        distance=distance,
        n_rounds=n_rounds,
        model=SimpleNamespace(
            version=spec.model_version,
            # Inference: dropout off; activation must match training (gelu per NVIDIA configs)
            dropout_p=0.0,
            activation="gelu",
            input_channels=4,
            out_channels=4,
            num_filters=spec.num_filters,
            kernel_size=spec.kernel_size,
        ),
    )


def _load_model(variant: IsingVariant, distance: int, n_rounds: int, device: torch.device) -> torch.nn.Module:
    """Build the predecoder model + load safetensors weights, cached per process."""
    _ensure_nvidia_path()
    from model.predecoder import PreDecoderModelMemory_v1  # type: ignore
    from safetensors.torch import load_file

    key = (variant.backend_name, distance, n_rounds, device.index if device.index is not None else -1)
    with _MODEL_CACHE_LOCK:
        if key in _MODEL_CACHE:
            return _MODEL_CACHE[key]

        cfg = _build_model_cfg(distance, n_rounds, variant.model_id)
        model = PreDecoderModelMemory_v1(cfg)
        state_dict = load_file(str(variant.weights_path))
        # Weights are fp16; cast to fp32 for the eager-mode forward path.
        state_dict_fp32 = {k: v.to(torch.float32) for k, v in state_dict.items()}
        missing, unexpected = model.load_state_dict(state_dict_fp32, strict=False)
        if missing or unexpected:
            logger.warning(
                "%s: load_state_dict missing=%d unexpected=%d (first missing: %s)",
                variant.backend_name,
                len(missing),
                len(unexpected),
                missing[:1],
            )

        model = model.to(device).eval()
        _MODEL_CACHE[key] = model
        logger.info(
            "%s loaded: %d params on %s",
            variant.backend_name,
            sum(p.numel() for p in model.parameters()),
            device,
        )
        return model


@dataclass(frozen=True)
class _StabMaps:
    Hx_idx: torch.Tensor      # (Sx, Kx) long, parity-check column indices
    Hz_idx: torch.Tensor      # (Sz, Kz) long
    Hx_mask: torch.Tensor     # (Sx, Kx) bool
    Hz_mask: torch.Tensor     # (Sz, Kz) bool
    Kx: int
    Kz: int
    stab_indices_x: torch.Tensor  # (Sx,) long, grid -> stabilizer
    stab_indices_z: torch.Tensor
    Lx: torch.Tensor          # (1, D²) int32, X logical operator
    Lz: torch.Tensor          # (1, D²) int32, Z logical operator


def _build_stab_maps(distance: int, rotation: str, device: torch.device) -> _StabMaps:
    """Build all parity-check, stabilizer-index, and logical-operator tensors."""
    _ensure_nvidia_path()
    from evaluation.logical_error_rate import _build_stab_maps as _nv_build  # type: ignore

    maps = _nv_build(distance, rotation)
    D2 = distance * distance

    Lx = torch.zeros((1, D2), dtype=torch.int32, device=device)
    Lz = torch.zeros((1, D2), dtype=torch.int32, device=device)
    if rotation.upper() in ("XV", "ZH"):
        Lx[0, :distance] = 1
        Lz[0, ::distance] = 1
    else:
        Lx[0, ::distance] = 1
        Lz[0, :distance] = 1

    return _StabMaps(
        Hx_idx=maps["Hx_idx"].to(device=device, dtype=torch.long),
        Hz_idx=maps["Hz_idx"].to(device=device, dtype=torch.long),
        Hx_mask=maps["Hx_mask"].to(device=device, dtype=torch.bool),
        Hz_mask=maps["Hz_mask"].to(device=device, dtype=torch.bool),
        Kx=int(maps["Kx"]),
        Kz=int(maps["Kz"]),
        stab_indices_x=maps["stab_x"].to(device=device, dtype=torch.long),
        stab_indices_z=maps["stab_z"].to(device=device, dtype=torch.long),
        Lx=Lx,
        Lz=Lz,
    )


def _compute_parity_sum(
    data_corr_flat: torch.Tensor,  # (B, D2, T) int32 — z_data_corr or x_data_corr flattened
    H_idx: torch.Tensor,           # (S, K) long
    H_mask: torch.Tensor,          # (S, K) bool
    K: int,
) -> torch.Tensor:
    """Compute S = (H @ data_corr) mod 2 in (B, S, T) form."""
    B, D2, T = data_corr_flat.shape
    expanded = data_corr_flat.unsqueeze(2).expand(B, D2, K, T)
    H_idx_e = H_idx.clamp_min(0).view(1, -1, K, 1).expand(B, -1, -1, T)
    gathered = expanded.gather(dim=1, index=H_idx_e)
    mask = H_mask.view(1, -1, K, 1).expand_as(gathered)
    return (gathered.masked_fill(~mask, 0).sum(dim=2) & 1)


def _compute_residual_full(
    logits: torch.Tensor,             # (B, 4, T, D, D)
    x_syn_diff: torch.Tensor,         # (B, half, T)
    z_syn_diff: torch.Tensor,
    detection_events: torch.Tensor,   # (B, num_detectors), original
    num_boundary_dets: int,
    maps: _StabMaps,
    distance: int,                    # noqa: ARG001 - kept for symmetry / future use
    basis: str,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Full predecoder ensemble: residual + pre_L.

    Implements the four-channel pipeline per NVIDIA's _model_forward_and_residual:
      - logits[:, 0] -> z_data_corr  (Z errors on data qubits)
      - logits[:, 1] -> x_data_corr  (X errors on data qubits)
      - logits[:, 2] -> syn_x_grid   (X stabilizer measurement errors)
      - logits[:, 3] -> syn_z_grid   (Z stabilizer measurement errors)

    Returns (residual_uint8, pre_L_int32) where:
      - residual: (B, num_detectors) uint8, fed to PyMatching
      - pre_L: (B,) int32, logical frame contribution from data corrections,
        XORed with PyMatching's prediction to produce the final logical answer.
    """
    _ensure_nvidia_path()
    from qec.surface_code.data_mapping import map_grid_to_stabilizer_tensor  # type: ignore

    _ = distance  # caller-supplied; we read shape from the logits tensor instead
    B, _, T, D, _ = logits.shape
    D2 = D * D

    # Threshold logits to binary predictions (deterministic mode, threshold=0)
    z_data_corr = (logits[:, 0] >= 0).to(torch.int32)  # (B, T, D, D)
    x_data_corr = (logits[:, 1] >= 0).to(torch.int32)
    syn_x_grid = (logits[:, 2] >= 0).to(torch.int32)
    syn_z_grid = (logits[:, 3] >= 0).to(torch.int32)

    # Flatten data corrections to (B, D2, T)
    z_flat = z_data_corr.permute(0, 2, 3, 1).contiguous().view(B, D2, T)
    x_flat = x_data_corr.permute(0, 2, 3, 1).contiguous().view(B, D2, T)

    # Parity sums induced by data corrections
    S_X = _compute_parity_sum(z_flat, maps.Hx_idx, maps.Hx_mask, maps.Kx)  # (B, Sx, T)
    S_Z = _compute_parity_sum(x_flat, maps.Hz_idx, maps.Hz_mask, maps.Kz)  # (B, Sz, T)

    # Predecoder's stabilizer-error predictions in stabilizer-flat form
    syn_x_flat = map_grid_to_stabilizer_tensor(syn_x_grid, maps.stab_indices_x).to(torch.int32)
    syn_z_flat = map_grid_to_stabilizer_tensor(syn_z_grid, maps.stab_indices_z).to(torch.int32)

    # Time-recurrent residual: R_t = original_diff[t] + pred[t] + pred[t-1] + S[t]  (mod 2)
    R_X = torch.empty_like(x_syn_diff, dtype=torch.int32)
    R_X[:, :, 0] = (x_syn_diff[:, :, 0] + syn_x_flat[:, :, 0] + S_X[:, :, 0]) & 1
    if T > 1:
        R_X[:, :, 1:] = (
            x_syn_diff[:, :, 1:] + syn_x_flat[:, :, 1:] + syn_x_flat[:, :, :-1] + S_X[:, :, 1:]
        ) & 1

    R_Z = torch.empty_like(z_syn_diff, dtype=torch.int32)
    R_Z[:, :, 0] = (z_syn_diff[:, :, 0] + syn_z_flat[:, :, 0] + S_Z[:, :, 0]) & 1
    if T > 1:
        R_Z[:, :, 1:] = (
            z_syn_diff[:, :, 1:] + syn_z_flat[:, :, 1:] + syn_z_flat[:, :, :-1] + S_Z[:, :, 1:]
        ) & 1

    # Logical-frame contribution from data corrections
    if basis == "X":
        pre_L_t = torch.einsum(
            "ld,bdt->blt",
            maps.Lx.to(torch.float32),
            z_flat.to(torch.float32),
        ).remainder_(2).to(torch.int32)
    else:
        pre_L_t = torch.einsum(
            "ld,bdt->blt",
            maps.Lz.to(torch.float32),
            x_flat.to(torch.float32),
        ).remainder_(2).to(torch.int32)
    pre_L = pre_L_t.sum(dim=2).remainder_(2).view(-1)

    # Detector layout: round-0 of basis, then (X, Z) for rounds 1..T-1, then boundary
    if basis == "X":
        initial_detectors = R_X[:, :, 0].view(B, -1)
    else:
        initial_detectors = R_Z[:, :, 0].view(B, -1)

    R_cat_rest = torch.cat([R_X[:, :, 1:], R_Z[:, :, 1:]], dim=1)
    rest_flat = R_cat_rest.permute(0, 2, 1).contiguous().view(B, -1)
    boundary = detection_events[:, -num_boundary_dets:].to(torch.int32)
    residual = torch.cat([initial_detectors, rest_flat, boundary], dim=1).to(torch.uint8)

    return residual, pre_L


def _decode_residual_pymatching(
    residual: np.ndarray,
    dem_str: str,
) -> np.ndarray:
    import pymatching
    import stim

    dem = stim.DetectorErrorModel(dem_str)
    matcher = pymatching.Matching.from_detector_error_model(dem)
    predictions = matcher.decode_batch(residual)
    return np.asarray(predictions, dtype=np.uint8)


def run_predecoder_pipeline(
    variant: IsingVariant,
    backend_input: BackendInput,
    gpu_lane: int | None,
) -> Solution:
    """End-to-end Ising predecoder + PyMatching pipeline.

    Returns a Solution with the same payload shape as the pymatching backend,
    so the QEC evaluator scores it on the same metric.
    """
    payload = backend_input.payload
    syndrome = payload.get("syndrome", {})

    trainX = syndrome.get("trainX")
    detection_events = syndrome.get("detection_events")
    observable_flips = syndrome.get("observable_flips")
    x_syn_diff = syndrome.get("x_syn_diff")
    z_syn_diff = syndrome.get("z_syn_diff")
    dem_str = syndrome.get("dem_str")
    distance = syndrome.get("distance")
    n_rounds = syndrome.get("n_rounds")
    basis = str(syndrome.get("basis", "X")).upper()
    rotation = str(syndrome.get("rotation", "XV")).upper()

    if any(x is None for x in (trainX, detection_events, x_syn_diff, z_syn_diff, dem_str)):
        return failed_solution(
            variant.backend_name,
            "Missing one of: trainX, detection_events, x_syn_diff, z_syn_diff, dem_str",
        )

    if not torch.cuda.is_available():
        return failed_solution(variant.backend_name, "CUDA not available")
    lane = 0 if gpu_lane is None else int(gpu_lane)
    if lane >= torch.cuda.device_count():
        return failed_solution(
            variant.backend_name,
            f"Requested gpu_lane={lane} but only {torch.cuda.device_count()} GPU(s) visible",
        )
    device = torch.device(f"cuda:{lane}")

    if not variant.weights_path.exists():
        return failed_solution(
            variant.backend_name,
            f"Weights not found at {variant.weights_path}",
        )

    start = time.perf_counter()
    try:
        model = _load_model(variant, int(distance), int(n_rounds), device)
        maps = _build_stab_maps(int(distance), rotation, device)

        # Move all tensors to GPU
        if not isinstance(trainX, torch.Tensor):
            trainX_t = torch.as_tensor(trainX, dtype=torch.float32)
        else:
            trainX_t = trainX.to(torch.float32)
        if not isinstance(x_syn_diff, torch.Tensor):
            x_syn_diff_t = torch.as_tensor(x_syn_diff, dtype=torch.int32)
        else:
            x_syn_diff_t = x_syn_diff.to(torch.int32)
        if not isinstance(z_syn_diff, torch.Tensor):
            z_syn_diff_t = torch.as_tensor(z_syn_diff, dtype=torch.int32)
        else:
            z_syn_diff_t = z_syn_diff.to(torch.int32)

        detection_events_t = torch.as_tensor(detection_events, dtype=torch.int32)

        trainX_t = trainX_t.to(device)
        x_syn_diff_t = x_syn_diff_t.to(device)
        z_syn_diff_t = z_syn_diff_t.to(device)
        detection_events_t = detection_events_t.to(device)

        D = int(distance)
        num_boundary_dets = (D * D - 1) // 2

        with torch.no_grad():
            t_fwd_start = time.perf_counter()
            logits = model(trainX_t)  # (B, 4, T, D, D)
            torch.cuda.synchronize(device)
            t_fwd_ms = int((time.perf_counter() - t_fwd_start) * 1000)

            residual, pre_L = _compute_residual_full(
                logits=logits,
                x_syn_diff=x_syn_diff_t,
                z_syn_diff=z_syn_diff_t,
                detection_events=detection_events_t,
                num_boundary_dets=num_boundary_dets,
                maps=maps,
                distance=D,
                basis=basis,
            )

        residual_np = residual.cpu().numpy().astype(np.uint8)
        pre_L_np = pre_L.cpu().numpy().astype(np.uint8)

        # Decode residual with PyMatching (same DEM as baseline backend)
        t_match_start = time.perf_counter()
        matching_predictions = _decode_residual_pymatching(residual_np, dem_str)
        t_match_ms = int((time.perf_counter() - t_match_start) * 1000)

        # Final logical prediction: matching's output XOR predecoder's logical contribution
        if matching_predictions.ndim == 1:
            matching_predictions = matching_predictions.reshape(-1, 1)
        predictions = (matching_predictions ^ pre_L_np.reshape(-1, 1)).astype(np.uint8)

    except Exception as e:
        wall_time_ms = int((time.perf_counter() - start) * 1000)
        logger.exception("%s: pipeline failed", variant.backend_name)
        return failed_solution(
            variant.backend_name,
            f"Pipeline error: {e}",
            wall_time_ms=wall_time_ms,
        )

    wall_time_ms = int((time.perf_counter() - start) * 1000)

    if predictions.ndim == 1:
        predictions = predictions.reshape(-1, 1)
    if observable_flips.ndim == 1:
        observable_flips = observable_flips.reshape(-1, 1)

    n_shots = int(predictions.shape[0])
    logger.info(
        "%s: forward=%dms matching=%dms total=%dms shots=%d gpu_lane=%d",
        variant.backend_name, t_fwd_ms, t_match_ms, wall_time_ms, n_shots, lane,
    )

    return Solution(
        backend_name=variant.backend_name,
        payload={
            "predictions": predictions,
            "observable_flips": observable_flips,
            "decode_time_ms": wall_time_ms,
            "forward_time_ms": t_fwd_ms,
            "matching_time_ms": t_match_ms,
            "decoder": f"NVIDIA Ising {variant.variant_label} (predecoder + MWPM, syn_only mode)",
            "shots": n_shots,
            "gpu_lane": lane,
            "model_id": variant.model_id,
        },
        wall_time_ms=wall_time_ms,
        success=True,
    )
