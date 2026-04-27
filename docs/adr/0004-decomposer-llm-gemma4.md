# ADR-0004: Gemma 4 31B as the Decomposer LLM

- **Status:** Accepted (model choice still authoritative; runtime/endpoint moved to ADR-0010)
- **Date:** 2026-04-26
- **Deciders:** rollik

> **Update (2026-04-26):** ADR-0010 supersedes the *runtime* implied by this
> ADR (Ollama-on-workstation, q8 quant). The model — Gemma 4 31B-it — is unchanged.
> Default runtime is now vLLM on xr7620 in bf16; local Ollama remains as fallback.

## Context

The Decomposer module (plan §5) converts natural-language asks into a typed problem-graph DAG. The LLM must:

1. Emit valid JSON consistently (no markdown fences, no prose).
2. Comply with the problem-graph schema (problem_class in {qec_syndrome, qubo_assignment, qubo_routing, qubo_portfolio}).
3. Run locally on the workstation (Ollama, no cloud API calls).
4. Complete in reasonable time (<30 s per ask for interactive use).

We benchmarked five locally-available models against a fixed five-prompt suite covering all four problem classes plus a decomposable multi-step ask.

## Decision

Use **`gemma4:31b-it-q8_0`** (Google Gemma 4, 31B params, Q8_0 quantization) as the default Decomposer LLM.

Benchmark results (2026-04-26):

| model | JSON valid | schema OK | median s | max s |
|---|---:|---:|---:|---:|
| `gemma4:31b-it-q8_0` | 100% | 80% | 16.56 | 21.38 |
| `gemma4:26b` | 60% | 40% | 7.94 | 12.62 |
| `nemotron-3-nano:30b` | 80% | 80% | 3.70 | 7.24 |
| `gpt-oss:20b` | 80% | 80% | 2.95 | 6.75 |
| `mistral-small3.2:latest` | 100% | 60% | 1.88 | 6.41 |

Gemma4:31b-it-q8_0 is the only model achieving 100% JSON validity with >=80% schema compliance. The 80% schema figure reflects failure on the compound multi-step ask (produced a single leaf instead of two). Single-leaf asks pass at 100%.

## Alternatives considered

- **`mistral-small3.2:latest`** — 100% JSON validity but only 60% schema compliance. Faster (1.88 s median) but misclassified the routing prompt. For latency-critical paths we could fall back to Mistral with a retry loop, but the extra complexity isn't justified for Phase-0.

- **`nemotron-3-nano:30b`** — 80% JSON, 80% schema, fast (3.70 s median). The 20% JSON failure rate would require retry logic and user-facing error handling. Nemotron was our backup if Gemma 4 weights weren't Apache-2.0-licensed, but they are.

- **`gpt-oss:20b`** — Same 80/80 profile as Nemotron, slightly faster. JSON failures on the compound ask disqualify it for Phase-0 where we want the simplest code path.

- **Cloud-hosted models (Claude, GPT-4o, Gemini)** — Would trivially hit 100%/100% but introduce latency (network round-trip), cost, and data-residency concerns for Federal demos. The plan explicitly requires local weights.

## Consequences

### Positive

- Single code path with no retry logic for JSON parsing.
- Gemma 4 is Apache-2.0 licensed — no usage restrictions for demos or redistribution.
- Q8_0 quantization fits in ~34 GB VRAM; leaves headroom on the 48 GB RTX 6000 Ada for concurrent solver loads.
- Median latency of 16 s is acceptable for interactive notebook use.

### Negative / accepted trade-offs

- The compound multi-step ask (qec + assignment in sequence) fails schema validation. Phase-1 work will add explicit multi-step prompting or a second decomposition pass.
- 21 s max latency on complex asks may feel slow in the dashboard. We can add a spinner and async dispatch.
- Upgrading Gemma 4 minor versions may require re-benchmarking.

## References

- Bench results: `runs/smoke/decomposer_bench_20260426T113538Z.md`
- Gemma 4 model card: https://huggingface.co/google/gemma-4
- Ollama model library: https://ollama.com/library/gemma4
