"""Bench candidate Decomposer LLMs against a fixed prompt suite.

The Decomposer's job (plan §5) is to turn a natural-language ask into a typed
problem-graph DAG. Phase-0 / ADR-0004 needs three numbers per candidate:

    1. JSON-validity rate     — fraction of responses that parse as JSON
    2. schema-compliance rate — fraction that match our problem-graph schema
    3. wall-time per response — for steady-state cost tracking

We hit the locally-running Ollama daemon directly (no LiteLLM hop). Models
already pulled to Ollama are eligible; ones that aren't are skipped with a
note in the summary.

Output:
    runs/smoke/decomposer_bench_<UTC>.json — per-prompt records
    runs/smoke/decomposer_bench_<UTC>.md   — markdown summary table
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics as stats
import sys
import time
from pathlib import Path

import requests

OLLAMA_URL = "http://localhost:11434"
VLLM_URL = "http://10.0.100.69:8050"
VLLM_MODEL = "/weights/gemma-4-31B-it"

# Plan §3 names "gemma4:31b-it-q8_0" as the default and lists kimi-k2.6 /
# deepseek-r1 / nemotron-3-super as comparators. Of those, only nemotron-3 is
# available locally on the workstation as `nemotron-3-nano:30b`; kimi-k2.6 and
# deepseek-r1 weren't pulled. We bench what's there and document the gap in
# ADR-0004 instead of pulling 100s of GB on a Phase-0 budget.
CANDIDATES: list[str] = [
    "gemma4:31b-it-q8_0",   # plan default (anchor)
    "gemma4:26b",           # lighter Gemma 4 (q4_K_M)
    "nemotron-3-nano:30b",  # closest available Nemotron variant
    "gpt-oss:20b",          # OpenAI open-weights, MXFP4
    "mistral-small3.2:latest",  # 24B, fast JSON emitter in our experience
]

# Five fixed prompts spanning the four problem_class values plus an
# intentionally-decomposable multi-step ask.
PROMPTS: list[dict[str, str | None]] = [
    {
        "name": "qec_d5_p1e3",
        "ask": "Decode a distance-5 surface code at depolarizing noise rate p=1e-3.",
        "expect_class": "qec_syndrome",
    },
    {
        "name": "assign_12x8",
        "ask": "Assign 12 assets across 8 tasks with capacity constraint K=3.",
        "expect_class": "qubo_assignment",
    },
    {
        "name": "route_15_stop",
        "ask": "Plan a 15-stop delivery route minimizing total distance with one vehicle.",
        "expect_class": "qubo_routing",
    },
    {
        "name": "portfolio_30",
        "ask": "Pick a 30-asset portfolio from the S&P 100 minimizing risk at 8% target return.",
        "expect_class": "qubo_portfolio",
    },
    {
        "name": "compound_qec_then_assign",
        "ask": "First decode a distance-3 surface code at p=5e-4, then use the corrected logical to choose between 4 task-assignment strategies for 6 assets x 4 tasks.",
        "expect_class": None,  # decomposable — the graph should have >1 leaf
    },
]

SYSTEM_PROMPT = """You decompose a natural-language ask into a problem-graph DAG.
Reply with ONLY a JSON object (no prose, no fences) matching this schema:

{
  "problems": [
    {
      "problem_id": "p0",                    // unique short id
      "parent_id": null,                     // null for root, otherwise parent's problem_id
      "problem_class": "qec_syndrome|qubo_assignment|qubo_routing|qubo_portfolio",
      "params": { ... }                      // class-specific parameters
    },
    ...
  ]
}

Rules:
- Use ONLY the four problem_class values above.
- Every leaf must have problem_class set.
- Do not output anything before or after the JSON object.
"""

ALLOWED_CLASSES = {"qec_syndrome", "qubo_assignment", "qubo_routing", "qubo_portfolio"}


def list_local_models() -> set[str]:
    r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
    r.raise_for_status()
    return {m["name"] for m in r.json().get("models", [])}


def call_ollama(model: str, ask: str, timeout: float = 240.0) -> tuple[str, float]:
    """Returns (raw_text, wall_seconds). Uses /api/chat with format=json."""
    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.0, "num_predict": 1024},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": ask},
        ],
    }
    t0 = time.perf_counter()
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=timeout)
    dt_s = time.perf_counter() - t0
    r.raise_for_status()
    return r.json()["message"]["content"], dt_s


def call_vllm(model: str, ask: str, timeout: float = 240.0) -> tuple[str, float]:
    """Returns (raw_text, wall_seconds). Uses OpenAI-compatible /v1/chat/completions."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": ask},
        ],
        "temperature": 0.0,
        "max_tokens": 1024,
        "response_format": {"type": "json_object"},
    }
    t0 = time.perf_counter()
    r = requests.post(
        f"{VLLM_URL}/v1/chat/completions",
        json=payload,
        timeout=timeout,
        headers={"Authorization": "Bearer not-needed"},
    )
    dt_s = time.perf_counter() - t0
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"], dt_s


def call_endpoint(endpoint: str, model: str, ask: str) -> tuple[str, float]:
    if endpoint == "vllm":
        return call_vllm(model, ask)
    return call_ollama(model, ask)


def grade(raw: str, expect_class: str | None) -> dict:
    """Score a single response. Returns dict with json_valid/schema_ok flags."""
    out = {"json_valid": False, "schema_ok": False, "leaf_count": 0, "error": None}
    try:
        obj = json.loads(raw)
        out["json_valid"] = True
    except json.JSONDecodeError as e:
        out["error"] = f"json: {e}"
        return out

    problems = obj.get("problems")
    if not isinstance(problems, list) or not problems:
        out["error"] = "missing or empty 'problems' list"
        return out

    leaves = []
    seen_ids = set()
    for p in problems:
        if not isinstance(p, dict):
            out["error"] = "non-dict problem entry"
            return out
        pid = p.get("problem_id")
        cls = p.get("problem_class")
        if not pid or pid in seen_ids:
            out["error"] = f"duplicate or missing problem_id near {p}"
            return out
        seen_ids.add(pid)
        if cls not in ALLOWED_CLASSES and cls is not None:
            out["error"] = f"bad problem_class: {cls}"
            return out
        # leaf := no other problem references this one as parent
        leaves.append(pid)

    parents = {p.get("parent_id") for p in problems if p.get("parent_id")}
    leaves = [pid for pid in seen_ids if pid not in parents]
    out["leaf_count"] = len(leaves)

    if expect_class is not None:
        # single-leaf ask: verify the (sole) leaf carries the expected class
        leaf_classes = {
            p["problem_class"] for p in problems if p["problem_id"] in leaves
        }
        if expect_class in leaf_classes:
            out["schema_ok"] = True
        else:
            out["error"] = f"expected leaf class {expect_class}, got {leaf_classes}"
    else:
        # decomposable ask: pass if there are 2+ leaves with valid classes
        out["schema_ok"] = out["leaf_count"] >= 2

    return out


def bench_model(model: str, endpoint: str = "ollama") -> dict:
    label = f"{model} ({endpoint})"
    print(f"\n  {label}")
    rows = []
    for prompt in PROMPTS:
        ask = prompt["ask"]
        assert ask is not None
        try:
            raw, dt_s = call_endpoint(endpoint, model, ask)
            g = grade(raw, prompt["expect_class"])
            print(
                f"    {prompt['name']:<28}  {dt_s:6.2f}s  "
                f"json={'OK' if g['json_valid'] else 'NO ':<3}  "
                f"schema={'OK' if g['schema_ok'] else 'NO'}  "
                f"leaves={g['leaf_count']}"
            )
            rows.append(
                {
                    "prompt": prompt["name"],
                    "wall_seconds": dt_s,
                    "raw_response": raw,
                    **g,
                }
            )
        except Exception as e:  # noqa: BLE001
            print(f"    {prompt['name']:<28}  ERROR: {e!s}")
            rows.append(
                {"prompt": prompt["name"], "error": str(e), "wall_seconds": None,
                 "json_valid": False, "schema_ok": False, "leaf_count": 0}
            )
    n = len(rows)
    json_rate = sum(r["json_valid"] for r in rows) / n
    schema_rate = sum(r["schema_ok"] for r in rows) / n
    walls = [r["wall_seconds"] for r in rows if r.get("wall_seconds") is not None]
    return {
        "model": model,
        "endpoint": endpoint,
        "json_valid_rate": json_rate,
        "schema_ok_rate": schema_rate,
        "median_wall_seconds": stats.median(walls) if walls else None,
        "max_wall_seconds": max(walls) if walls else None,
        "rows": rows,
    }


def write_summary(results: list[dict], out_path: Path) -> None:
    lines = [
        "# Decomposer LLM bench",
        "",
        f"Run on {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')} UTC.",
        f"Endpoints: Ollama at {OLLAMA_URL}, vLLM at {VLLM_URL}.",
        "",
        "| model | endpoint | JSON valid | schema OK | median s | max s |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for r in results:
        med = "-" if r["median_wall_seconds"] is None else f"{r['median_wall_seconds']:.2f}"
        mx = "-" if r["max_wall_seconds"] is None else f"{r['max_wall_seconds']:.2f}"
        endpoint = r.get("endpoint", "ollama")
        lines.append(
            f"| `{r['model']}` | {endpoint} | {r['json_valid_rate']:.0%} | "
            f"{r['schema_ok_rate']:.0%} | {med} | {mx} |"
        )
    lines.append("")
    lines.append("Per-prompt details: see the matching `.json` file.")
    out_path.write_text("\n".join(lines) + "\n")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", default="runs/smoke", type=Path)
    p.add_argument("--models", nargs="*", help="override candidate list")
    p.add_argument(
        "--endpoint",
        choices=["ollama", "vllm", "both"],
        default="both",
        help="Which endpoint(s) to bench. 'both' covers Ollama on the workstation "
             "and vLLM on xr7620 (ADR-0010).",
    )
    args = p.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    skipped: list[str] = []

    if args.endpoint in ("ollama", "both"):
        available = list_local_models()
        candidates = args.models or CANDIDATES
        eligible = [m for m in candidates if m in available]
        skipped = [m for m in candidates if m not in available]
        print(f"Ollama models available locally: {len(available)}")
        if skipped:
            print(f"Skipping (not pulled): {', '.join(skipped)}")
        if eligible:
            print(f"Benching via Ollama: {', '.join(eligible)}")
            results.extend(bench_model(m, "ollama") for m in eligible)
        else:
            print("No Ollama candidates pulled.")

    if args.endpoint in ("vllm", "both"):
        print(f"Benching via vLLM at {VLLM_URL}: {VLLM_MODEL}")
        try:
            results.append(bench_model(VLLM_MODEL, "vllm"))
        except Exception as e:
            print(f"vLLM bench skipped: {e}")

    if not results:
        print("No models benched.")
        return 2

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = args.out_dir / f"decomposer_bench_{stamp}.json"
    md_path = args.out_dir / f"decomposer_bench_{stamp}.md"
    json_path.write_text(json.dumps({"skipped": skipped, "results": results}, indent=2))
    write_summary(results, md_path)

    print(f"\nWrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
