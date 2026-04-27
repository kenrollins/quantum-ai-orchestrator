# ADR-0010: Decomposer runtime — vLLM on xr7620 (default), Ollama on workstation (fallback)

- **Status:** Accepted
- **Date:** 2026-04-26
- **Deciders:** rollik

## Context

ADR-0004 locked the Decomposer model: `gemma4:31b-it` (bf16/q8 — same weights either runtime). That decision stands. Phase-1 work surfaced two operational problems with the runtime we picked at the time (Ollama on the workstation):

1. **Resource contention.** Ollama on the workstation is shared infrastructure: the gemma4:31b-it model alone occupies ~44 GB on GPU0 and ~10 GB on GPU1, plus other resident processes (`chipper`, etc.). Phase-1 added Ising decoders that also want GPU0/GPU1; under load, the LLM can OOM the Ising backend or vice versa. Hard to predict, hard to debug.
2. **Tool-calling and JSON-schema constraint defects.** `gemma4` via Ollama 0.20.5:
   - Schema-constrained generation (`format=<json_schema>`) reliably returns HTTP 500 from the API. Reproducible via curl independent of our pipeline. We worked around with loose `format: "json"` and a forgiving parser that absorbs Gemma's drift (`id` → `problem_id`, `class` → `problem_class`, `skill` leaking inside the first problem).
   - Tool calling works for simple cases but is ~9× slower wall-time than vLLM on the same prompt with the same model weights.

With Phase-1 racing six backends per ask, the LLM is the slowest stage and the most fragile one. A dedicated runtime fixes both problems.

The host has a Dell PowerEdge XR7620 (`gemma-forge`, `10.0.100.69`) running gemma4:31b-it in bf16 on 4× NVIDIA L4 with TP=4 under vLLM, exposed at `http://10.0.100.69:8050/v1`. Always-on systemd unit `gemma4-31b-vllm.service`, host-managed; we are a client only.

## Decision

**Default Decomposer endpoint: `http://10.0.100.69:8050/v1` (vLLM on xr7620).**
**Fallback: `http://localhost:11434/v1` (Ollama on the workstation).**

Configuration via environment variables:

```text
DECOMPOSER_BASE_URL=http://10.0.100.69:8050/v1
DECOMPOSER_MODEL=/weights/gemma-4-31B-it
DECOMPOSER_FALLBACK_URL=http://localhost:11434/v1
DECOMPOSER_FALLBACK_MODEL=gemma4:31b-it-q8_0
```

`orchestrator/pipeline/decomposer.py` will be refactored to:

1. Use the OpenAI Async client (vLLM-native API) instead of the Ollama-native API we currently call.
2. Try `DECOMPOSER_BASE_URL` first; on connection error or 5xx, fall back to `DECOMPOSER_FALLBACK_URL` with the same prompt + a one-shot retry budget.
3. Drop the loose-JSON-mode + forgiving-parser path *for the vLLM path* — vLLM emits clean canonical schema (verified across 5 runs of the production prompt). Keep the forgiving parser only on the Ollama fallback.

## Evidence

### Spot smokes (`tests/smoke/decomposer-remote/`, 2026-04-26)

| smoke | result |
|---|---|
| `01_models.json` | vLLM `/v1/models` returns `/weights/gemma-4-31B-it` |
| `02_chat.json` | "reply OK" → "OK" in **171 ms** wall (vs ~3-15 s on Ollama for the same call) |
| `03_decomposer_smoke.json` | 5/5 production-prompt runs, all parse cleanly. TTFT median **143 ms**, TTC median **7143 ms**, **14.7 t/s**. Schema is canonical (no shape drift). |
| `04_tool_call.json` | `build_qubo` tool-call: vLLM **2038 ms**, args parsed clean. Ollama 18451 ms, args parsed clean. **9× faster wall-time on vLLM.** |

### Formal bench (`runs/smoke/decomposer_bench_20260426T170616Z.md`)

Same model (gemma4 31B-it, q8 on Ollama / bf16 on vLLM) across the five-prompt suite from ADR-0004 (four canonical problem classes + one decomposable multi-step ask):

| endpoint | JSON valid | schema OK | median s | max s |
|---|---:|---:|---:|---:|
| Ollama (local q8) | 100% | 80% | **16.90** | 18.67 |
| vLLM (xr7620 bf16) | 100% | 80% | **7.47** | 11.21 |

Per-prompt: vLLM is 2.1× to 2.7× faster on every single ask. Schema-compliance is identical: both fail the same prompt (the compound multi-step ask, which returns a single leaf instead of a multi-leaf graph). That failure is in the *prompt*, not the runtime, and reproduces on both endpoints — a Phase-2 follow-up unrelated to this ADR.

## Alternatives considered

- **Stay on local Ollama only.** Avoids any cross-host dependency. Rejected because (a) the GPU contention with the Ising backends is real and growing, (b) the JSON-schema 500 bug means we lose the strongest correctness lever and rely on prompt + parser hacks, (c) the 9× tool-call speedup is meaningful when each ask round-trips ≥1 LLM call.
- **Run vLLM locally on the workstation.** Eliminates the network hop. Rejected because the workstation's GPUs are already booked: each backend race assigns one GPU lane, and the dashboard literalizes 2-GPU racing in the Bake-off panel. Adding vLLM steals capacity from the demo.
- **Cloud-hosted Gemma (Vertex AI / etc.).** Trivial latency, zero ops. Rejected on Federal data-residency grounds (per ADR-0004) — local-or-on-prem only.
- **Smaller model on local Ollama.** mistral-small3.2 was 8× faster but only 60% schema-compliant per ADR-0004. Doesn't solve the contention problem either. Not worth retrying.

## Consequences

### Positive

- Decomposer wall-time drops from ~14-17 s (Ollama) to ~7 s (vLLM) on the production prompt. End-to-end ask latency improves correspondingly.
- Streaming TTFT 143 ms makes the dashboard "thinking…" stage feel snappy instead of dead.
- Tool-call support is first-class via vLLM's `--tool-call-parser gemma4`. We can move skill-specific parameter extraction from the system-prompt-and-pray approach to typed tool calls. Phase-1 doesn't need this, but Phase-2 will.
- vLLM emits canonical-schema JSON without per-model shape patching. Forgiving parser becomes Ollama-only.
- LLM resource contention with Ising/CUDA-Q backends on the workstation goes away — they live on different machines now.
- Failure mode is explicit (network unreachable / 5xx) and recoverable (fallback to Ollama).

### Negative / accepted trade-offs

- **Soft network dependency.** If the link to xr7620 drops mid-decompose, we fail over to Ollama. If both fail, the pipeline aborts. The dashboard will surface "fallback engaged" so demos remain transparent.
- **Less direct control over the runtime.** xr7620 is host-managed; we cannot patch vLLM or pin models from the orchestrator side. If the host upgrades vLLM and breaks the gemma4 tool-call parser, we go back to Ollama until the regression is fixed upstream.
- **Latency floor includes the network RTT** (negligible on-LAN, ~0.5-1 ms; meaningful from off-site demo runs over a VPN).
- **Two endpoints to bench.** `tools/bench_decomposers.sh` needs to test both and report degradation when fallback is in use.

## References

- ADR-0004: Gemma 4 31B Q8 model selection. Still authoritative on *which model*; this ADR only changes *where it runs*.
- Smoke artifacts: `tests/smoke/decomposer-remote/{01_models.json, 02_chat.json, 03_decomposer_smoke.{py,json}, 04_tool_call.{py,json}}`
- vLLM systemd unit (host-managed, do-not-touch): `gemma4-31b-vllm.service` on xr7620.
