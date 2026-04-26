#!/usr/bin/env bash
# Bench candidate Decomposer LLMs on a fixed prompt suite.
#
# Plan §3 / ADR-0004: the Decomposer must reliably emit a JSON problem-graph
# DAG from a natural-language ask. We benchmark JSON-validity rate, schema
# compliance, and latency across a set of locally-pulled Ollama models.
#
# Output: runs/smoke/decomposer_bench_<timestamp>.json + .md summary.
set -euo pipefail

cd "$(dirname "$0")/.."

OUT_DIR="${OUT_DIR:-runs/smoke}"
mkdir -p "$OUT_DIR"

uv run python tools/bench_decomposers.py "$@" --out-dir "$OUT_DIR"
