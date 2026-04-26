#!/usr/bin/env bash
# Pull NVIDIA Ising Decoding open weights to /data/models/nvidia-ising/.
#
# Two surface-code decoder variants live in separate HF repos:
#   nvidia/Ising-Decoder-SurfaceCode-1-Fast       ~speed variant     (≈4 GB FP16)
#   nvidia/Ising-Decoder-SurfaceCode-1-Accurate   ~accuracy variant  (≈12 GB FP16)
#
# Both repos are gated=auto on HuggingFace (click-through, auto-approve). Using
# the HF token from ~/.cache/huggingface/token (set via `hf auth login`).
# Cached out of repo per .gitignore.
set -euo pipefail

DEST_ROOT="${ISING_WEIGHTS_DIR:-/data/models/nvidia-ising}"
REPOS=(
  "nvidia/Ising-Decoder-SurfaceCode-1-Fast:fast"
  "nvidia/Ising-Decoder-SurfaceCode-1-Accurate:accurate"
)

mkdir -p "$DEST_ROOT"

# Use the project's uv venv so `hf` resolves to huggingface_hub installed
# there, not whatever pyenv shim happens to be active. The venv is created
# with `make venv install`.
cd "$(dirname "$0")/.."
if ! uv run --quiet python -c "import huggingface_hub" 2>/dev/null; then
  echo "huggingface_hub not in the project venv. Run 'make install' first." >&2
  exit 2
fi

for entry in "${REPOS[@]}"; do
  repo="${entry%%:*}"
  variant="${entry##*:}"
  dest="$DEST_ROOT/$variant"
  mkdir -p "$dest"
  echo
  echo "=== $repo -> $dest ==="
  uv run hf download "$repo" --local-dir "$dest"
done

echo
echo "Done. Tree:"
du -sh "$DEST_ROOT"/* 2>/dev/null || true
