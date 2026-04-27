"""Smoke 4: tool-call support comparison.

Defines a single typed tool ('build_qubo') and a prompt that should trigger it.
Compares the response shape between:

  - vLLM at http://10.0.100.69:8050/v1 (with --enable-auto-tool-choice
    --tool-call-parser gemma4)
  - Ollama at http://localhost:11434/v1 (OpenAI-compat shim)

The point of this test is to verify which endpoint emits a clean OpenAI
`tool_calls` array (the gemma4 parser in vLLM is the entire reason we'd
prefer the remote endpoint over local Ollama).
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from openai import AsyncOpenAI

VLLM_BASE_URL = "http://10.0.100.69:8050/v1"
VLLM_MODEL = "/weights/gemma-4-31B-it"
OLLAMA_BASE_URL = "http://localhost:11434/v1"
OLLAMA_MODEL = "gemma4:31b-it-q8_0"

OUTPUT = Path(__file__).parent / "04_tool_call.json"

TOOL = {
    "type": "function",
    "function": {
        "name": "build_qubo",
        "description": "Construct a QUBO problem for an asset-to-task assignment.",
        "parameters": {
            "type": "object",
            "properties": {
                "assets": {"type": "integer", "description": "Number of assets to assign"},
                "tasks": {"type": "integer", "description": "Number of tasks to cover"},
                "capacity": {
                    "type": "integer",
                    "description": "Maximum tasks one asset can take",
                },
                "seed": {"type": "integer", "description": "Random seed for reproducibility"},
            },
            "required": ["assets", "tasks", "capacity"],
        },
    },
}

PROMPT = (
    "I need to assign 12 assets across 8 tasks. Each asset should not handle more "
    "than 3 tasks. Use seed 42 for reproducibility. Build the QUBO."
)


async def call(label: str, base_url: str, model: str) -> dict:
    client = AsyncOpenAI(base_url=base_url, api_key="not-needed")
    print(f"\n=== {label} ({base_url}) ===")
    t0 = time.perf_counter()
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": PROMPT}],
            tools=[TOOL],
            tool_choice="auto",
            temperature=0.0,
            max_tokens=512,
        )
    except Exception as e:
        print(f"  ERROR: {e}")
        return {"endpoint": base_url, "error": str(e), "elapsed_ms": int((time.perf_counter() - t0) * 1000)}

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    msg = resp.choices[0].message
    tool_calls = []
    if getattr(msg, "tool_calls", None):
        for tc in msg.tool_calls:
            tool_calls.append({
                "id": tc.id,
                "type": tc.type,
                "name": tc.function.name,
                "arguments_raw": tc.function.arguments,
                "arguments_parsed": _try_parse_json(tc.function.arguments),
            })

    print(f"  elapsed_ms: {elapsed_ms}")
    print(f"  finish_reason: {resp.choices[0].finish_reason}")
    print(f"  content: {msg.content!r}")
    print(f"  tool_calls: {len(tool_calls)}")
    for tc in tool_calls:
        print(f"    -> {tc['name']}({tc['arguments_parsed']})")

    return {
        "endpoint": base_url,
        "model": model,
        "elapsed_ms": elapsed_ms,
        "finish_reason": resp.choices[0].finish_reason,
        "content": msg.content,
        "tool_calls": tool_calls,
        "tool_call_count": len(tool_calls),
        "first_call_args_clean": (
            tool_calls[0]["arguments_parsed"] is not None
            and "assets" in (tool_calls[0]["arguments_parsed"] or {})
        ) if tool_calls else False,
    }


def _try_parse_json(s):
    try:
        return json.loads(s) if s else None
    except Exception:
        return None


async def main():
    print("Tool-call smoke: build_qubo function")
    print(f"Prompt: {PROMPT!r}")
    print(f"Required args: assets={{12}}, tasks={{8}}, capacity={{3}}, seed={{42}}")

    vllm_result = await call("vLLM (xr7620)", VLLM_BASE_URL, VLLM_MODEL)
    ollama_result = await call("Ollama (local)", OLLAMA_BASE_URL, OLLAMA_MODEL)

    print("\n=== Summary ===")
    for label, r in [("vLLM", vllm_result), ("Ollama", ollama_result)]:
        if "error" in r:
            print(f"  {label}: ERROR — {r['error']}")
            continue
        n = r.get("tool_call_count", 0)
        clean = r.get("first_call_args_clean", False)
        print(
            f"  {label:8s} elapsed={r['elapsed_ms']}ms tool_calls={n} "
            f"args_clean={clean} finish={r['finish_reason']}"
        )

    OUTPUT.write_text(json.dumps({
        "prompt": PROMPT,
        "tool_schema": TOOL,
        "vllm": vllm_result,
        "ollama": ollama_result,
    }, indent=2, default=str))
    print(f"\n  artifact: {OUTPUT}")


if __name__ == "__main__":
    asyncio.run(main())
