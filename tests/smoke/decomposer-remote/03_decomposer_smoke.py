"""Smoke 3: Decomposer-shaped prompt against vLLM endpoint.

Sends the same SYSTEM_PROMPT the production decomposer uses, asks for a
JSON object describing 'decode a distance-5 surface code at p=1e-3',
parses it, and reports latencies.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import time
from pathlib import Path

from openai import AsyncOpenAI

from orchestrator.pipeline.decomposer import SYSTEM_PROMPT, _parse_response

VLLM_BASE_URL = "http://10.0.100.69:8050/v1"
VLLM_MODEL = "/weights/gemma-4-31B-it"
ASK = "decode a distance-5 surface code at p=1e-3"
OUTPUT = Path(__file__).parent / "03_decomposer_smoke.json"

NUM_RUNS = 5


async def one_run(client: AsyncOpenAI) -> dict:
    t_send = time.perf_counter()
    first_token_t: float | None = None
    chunks: list[str] = []
    completion_tokens = 0
    prompt_tokens = 0

    stream = await client.chat.completions.create(
        model=VLLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": ASK},
        ],
        temperature=0.1,
        stream=True,
        stream_options={"include_usage": True},
    )

    async for chunk in stream:
        if first_token_t is None and chunk.choices and chunk.choices[0].delta.content:
            first_token_t = time.perf_counter()
        if chunk.choices and chunk.choices[0].delta.content:
            chunks.append(chunk.choices[0].delta.content)
        if chunk.usage:
            completion_tokens = chunk.usage.completion_tokens
            prompt_tokens = chunk.usage.prompt_tokens

    t_end = time.perf_counter()
    content = "".join(chunks)

    parsed: dict | None = None
    parse_error: str | None = None
    try:
        parsed = _parse_response(content)
    except Exception as e:
        parse_error = str(e)

    ttft_ms = int((first_token_t - t_send) * 1000) if first_token_t else None
    ttc_ms = int((t_end - t_send) * 1000)
    tps = (completion_tokens / (t_end - t_send)) if t_end > t_send else None

    return {
        "ttft_ms": ttft_ms,
        "ttc_ms": ttc_ms,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "tokens_per_sec": round(tps, 2) if tps else None,
        "raw_content": content,
        "parsed": parsed,
        "parse_error": parse_error,
    }


async def main():
    client = AsyncOpenAI(base_url=VLLM_BASE_URL, api_key="not-needed")

    print(f"Endpoint: {VLLM_BASE_URL}")
    print(f"Model:    {VLLM_MODEL}")
    print(f"Ask:      {ASK!r}")
    print(f"Runs:     {NUM_RUNS}")
    print()

    results = []
    for i in range(NUM_RUNS):
        r = await one_run(client)
        ok = r["parsed"] is not None
        marker = "ok" if ok else "FAIL"
        print(
            f"  [{marker}] run {i+1}: ttft={r['ttft_ms']}ms ttc={r['ttc_ms']}ms "
            f"prompt={r['prompt_tokens']}t completion={r['completion_tokens']}t "
            f"tps={r['tokens_per_sec']}"
        )
        if r["parse_error"]:
            print(f"        parse_error: {r['parse_error']}")
        results.append(r)

    print()
    ttfts = [r["ttft_ms"] for r in results if r["ttft_ms"] is not None]
    ttcs = [r["ttc_ms"] for r in results]
    tpss = [r["tokens_per_sec"] for r in results if r["tokens_per_sec"]]
    if ttfts:
        print(f"  TTFT (ms): min={min(ttfts)} median={statistics.median(ttfts)} max={max(ttfts)}")
    print(f"  TTC  (ms): min={min(ttcs)} median={statistics.median(ttcs)} max={max(ttcs)}")
    if tpss:
        print(f"  tokens/s : min={min(tpss):.1f} median={statistics.median(tpss):.1f} max={max(tpss):.1f}")
    print()

    # Validate first run's parsed response structure
    first = results[0]
    if first["parsed"]:
        p = first["parsed"]
        print(f"  First parsed: skill={p.get('skill')} problems={len(p.get('problems', []))}")
        for prob in p.get("problems", []):
            print(f"    {prob.get('problem_id')}  class={prob.get('problem_class')}  params={prob.get('params')}")

    summary = {
        "endpoint": VLLM_BASE_URL,
        "model": VLLM_MODEL,
        "ask": ASK,
        "num_runs": NUM_RUNS,
        "stats": {
            "ttft_ms": {"min": min(ttfts), "median": statistics.median(ttfts), "max": max(ttfts)} if ttfts else None,
            "ttc_ms": {"min": min(ttcs), "median": statistics.median(ttcs), "max": max(ttcs)},
            "tokens_per_sec": {"min": min(tpss), "median": statistics.median(tpss), "max": max(tpss)} if tpss else None,
        },
        "all_parsed": all(r["parsed"] is not None for r in results),
        "runs": results,
    }
    OUTPUT.write_text(json.dumps(summary, indent=2, default=str))
    print(f"  artifact: {OUTPUT}")


if __name__ == "__main__":
    asyncio.run(main())
