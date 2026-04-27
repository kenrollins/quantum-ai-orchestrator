"""Decomposer: Natural language → Problem graph DAG.

Per ADR-0010 the default runtime is vLLM on xr7620; local Ollama is the
fallback for cases where the remote endpoint is unreachable. Both serve
gemma4:31b-it (bf16 on vLLM, q8 on Ollama) per ADR-0004.

The vLLM path uses the OpenAI-compatible API and trusts the model to emit
canonical schema directly (verified across the bench suite). The Ollama
fallback uses the looser native /api/chat endpoint and goes through a
forgiving parser that absorbs Gemma's shape drift on that runtime
("id" vs "problem_id", "class" vs "problem_class", "skill" leaking inside
the first problem). Schema-constrained generation via Ollama's `format`
field returns 500 for gemma4:31b-it on Ollama 0.20.5; we don't use it.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any
from uuid import uuid4

import httpx
from openai import APIConnectionError, APIStatusError, AsyncOpenAI

from .types import Problem, ProblemClass, ProblemGraph

logger = logging.getLogger(__name__)

# Default runtime — vLLM on xr7620 per ADR-0010
DECOMPOSER_BASE_URL = os.getenv(
    "DECOMPOSER_BASE_URL", "http://10.0.100.69:8050/v1"
)
DECOMPOSER_MODEL = os.getenv("DECOMPOSER_MODEL", "/weights/gemma-4-31B-it")

# Fallback — local Ollama. Only consulted when the primary fails or is unreachable.
DECOMPOSER_FALLBACK_URL = os.getenv(
    "DECOMPOSER_FALLBACK_URL", "http://localhost:11434/api/chat"
)
DECOMPOSER_FALLBACK_MODEL = os.getenv(
    "DECOMPOSER_FALLBACK_MODEL", "gemma4:31b-it-q8_0"
)

DECOMPOSER_TIMEOUT_S = float(os.getenv("DECOMPOSER_TIMEOUT_S", "180"))

# JSON schema for Decomposer output
PROBLEM_GRAPH_SCHEMA = {
    "type": "object",
    "properties": {
        "skill": {
            "type": "string",
            "enum": ["qec_decode", "mission_assignment", "routing", "portfolio"],
            "description": "Which skill handles this ask",
        },
        "problems": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "problem_id": {"type": "string"},
                    "problem_class": {
                        "type": "string",
                        "enum": ["qec_syndrome", "qubo_assignment", "qubo_routing", "qubo_portfolio"],
                    },
                    "params": {"type": "object"},
                    "parent_id": {"type": ["string", "null"]},
                },
                "required": ["problem_id", "problem_class", "params"],
            },
            "minItems": 1,
        },
    },
    "required": ["skill", "problems"],
}

SYSTEM_PROMPT = """You are the Decomposer for a hybrid quantum-classical orchestrator.

Given a natural-language ask, emit a JSON problem graph that downstream stages can execute. The format is enforced by a strict JSON schema; the keys MUST be exactly:

  - top-level "skill" (string)
  - top-level "problems" (array of objects)
  - each problem has: "problem_id" (string), "problem_class" (string), "params" (object), "parent_id" (string or null)

Skills:
  - qec_decode (quantum error correction)
  - mission_assignment (asset-to-task allocation)
  - routing (vehicle routing)
  - portfolio (portfolio optimization)

Problem classes and their params:
  - qec_syndrome:    {distance: int, noise_rate: float, shots: int, rounds?: int, basis?: "X"|"Z"}
  - qubo_assignment: {assets: int, tasks: int, capacity: int, seed?: int}
  - qubo_routing:    {stops: int, vehicles: int, depot?: int, seed?: int}
  - qubo_portfolio:  {assets: int, risk_aversion: float, cardinality?: int, seed?: int}

For simple asks, emit a single-problem graph with parent_id=null. For compound asks (multiple steps), link problems by parent_id. Extract every parameter the ask mentions; use sensible defaults for the rest.

Example for ask "decode a distance-5 surface code at p=1e-3":

{
  "skill": "qec_decode",
  "problems": [
    {
      "problem_id": "p1",
      "problem_class": "qec_syndrome",
      "params": {"distance": 5, "noise_rate": 0.001, "shots": 10000},
      "parent_id": null
    }
  ]
}

Respond with ONLY valid JSON matching the schema. No markdown, no explanation."""


def _build_messages(ask: str) -> list[dict[str, Any]]:
    """Build the chat messages for the decomposer call."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": ask},
    ]


_FIELD_ALIASES = {
    "problem_id": ("problem_id", "id"),
    "problem_class": ("problem_class", "class"),
    "params": ("params",),
    "parent_id": ("parent_id",),
}


def _pick_alias(d: dict[str, Any], canonical: str) -> Any:
    """Pull `canonical` from `d` accepting any of the known alias keys."""
    for key in _FIELD_ALIASES[canonical]:
        if key in d:
            return d[key]
    return None


def _normalize_problem(p: dict[str, Any], default_id: str) -> dict[str, Any]:
    """Coerce Gemma's drifted shapes into our canonical problem dict."""
    return {
        "problem_id": _pick_alias(p, "problem_id") or default_id,
        "problem_class": _pick_alias(p, "problem_class"),
        "params": _pick_alias(p, "params") or {},
        "parent_id": _pick_alias(p, "parent_id"),
    }


def _parse_response(content: str) -> dict[str, Any]:
    """Parse and validate the LLM response, absorbing common Gemma shape drift."""
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON from decomposer: {e}") from e

    if "problems" not in data or not data["problems"]:
        raise ValueError("Missing or empty 'problems' in decomposer output")

    # If skill is missing at top level but present in the first problem, lift it.
    if "skill" not in data:
        first = data["problems"][0] if isinstance(data["problems"][0], dict) else None
        if first and "skill" in first:
            data["skill"] = first["skill"]
        else:
            raise ValueError("Missing 'skill' in decomposer output")

    # Normalize each problem
    data["problems"] = [
        _normalize_problem(p, default_id=f"p{i + 1}")
        for i, p in enumerate(data["problems"])
        if isinstance(p, dict)
    ]
    if not data["problems"]:
        raise ValueError("Decomposer returned no parseable problems")

    # Drop any 'skill' that leaked into individual problems (we already lifted it)
    for p in data["problems"]:
        p.pop("skill", None)

    # Validate problem_class values
    valid_classes = {c.value for c in ProblemClass}
    for p in data["problems"]:
        if p["problem_class"] not in valid_classes:
            raise ValueError(
                f"Unknown problem_class {p['problem_class']!r} (valid: {sorted(valid_classes)})"
            )

    return data


def _to_problem_graph(run_id, ask_text: str, data: dict[str, Any]) -> ProblemGraph:
    """Convert parsed JSON to typed ProblemGraph."""
    problems = []
    for p in data["problems"]:
        problem_class = ProblemClass(p["problem_class"])
        problems.append(
            Problem(
                problem_id=p["problem_id"],
                problem_class=problem_class,
                params=p["params"],
                parent_id=p.get("parent_id"),
            )
        )

    return ProblemGraph(
        run_id=run_id,
        ask_text=ask_text,
        skill=data["skill"],
        problems=problems,
    )


async def _call_vllm(ask: str) -> str:
    """Hit the OpenAI-compatible vLLM endpoint and return raw response content."""
    # Tight connect timeout so a dead remote falls through to the Ollama fallback
    # quickly. Read timeout stays generous because gemma4 takes ~7s in the warm path.
    timeout = httpx.Timeout(connect=3.0, read=DECOMPOSER_TIMEOUT_S, write=10.0, pool=5.0)
    client = AsyncOpenAI(
        base_url=DECOMPOSER_BASE_URL,
        api_key="not-needed",
        timeout=timeout,
        max_retries=0,
    )
    resp = await client.chat.completions.create(
        model=DECOMPOSER_MODEL,
        messages=_build_messages(ask),  # type: ignore[arg-type]
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    if not resp.choices or resp.choices[0].message.content is None:
        raise ValueError(f"Empty response from vLLM: {resp}")
    return resp.choices[0].message.content


async def _call_ollama(ask: str) -> str:
    """Hit Ollama's native /api/chat endpoint as the fallback runtime."""
    payload = {
        "model": DECOMPOSER_FALLBACK_MODEL,
        "messages": _build_messages(ask),
        "stream": False,
        # Loose JSON mode; the schema-constrained variant 500s on Ollama 0.20.5.
        "format": "json",
        "options": {"temperature": 0.1},
    }
    async with httpx.AsyncClient(timeout=DECOMPOSER_TIMEOUT_S) as client:
        resp = await client.post(DECOMPOSER_FALLBACK_URL, json=payload)
        resp.raise_for_status()
        body = resp.json()
    content = body.get("message", {}).get("content")
    if not content:
        raise ValueError(f"Empty response from Ollama: {body}")
    return content


async def decompose(ask: str, run_id=None) -> ProblemGraph:
    """Convert natural language ask to a problem graph.

    Tries vLLM (default per ADR-0010); on connection error or 5xx, falls
    back to local Ollama with the same prompt. The forgiving parser absorbs
    Gemma's shape drift either way.

    Args:
        ask: Natural language description of the problem.
        run_id: UUID for this run (generated if not provided).

    Returns:
        ProblemGraph with one or more Problems.

    Raises:
        ValueError: If both runtimes fail or output cannot be parsed.
    """
    if run_id is None:
        run_id = uuid4()

    logger.info("Decomposing ask: %s", ask[:100])

    content: str | None = None
    runtime_used: str | None = None

    # Primary: vLLM. Catch network/transient errors and fall through.
    try:
        content = await _call_vllm(ask)
        runtime_used = f"vllm@{DECOMPOSER_BASE_URL}"
    except (APIConnectionError, APIStatusError, httpx.HTTPError, ValueError) as e:
        logger.warning(
            "Decomposer primary (vLLM) failed: %s. Falling back to Ollama.", e
        )

    if content is None:
        try:
            content = await _call_ollama(ask)
            runtime_used = f"ollama@{DECOMPOSER_FALLBACK_URL}"
        except Exception as e:
            raise RuntimeError(
                f"Decomposer failed on both vLLM and Ollama fallback: {e}"
            ) from e

    logger.debug("Raw decomposer response (via %s): %s", runtime_used, content[:500])

    data = _parse_response(content)
    graph = _to_problem_graph(run_id, ask, data)

    logger.info(
        "Decomposed via %s: skill=%s, %d problem(s)",
        runtime_used, graph.skill, len(graph.problems),
    )
    return graph


# Synchronous wrapper for CLI use
def decompose_sync(ask: str, run_id=None) -> ProblemGraph:
    """Synchronous version of decompose()."""
    import asyncio

    return asyncio.run(decompose(ask, run_id))
