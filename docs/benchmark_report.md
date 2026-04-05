# Benchmark Report

This report is set up for honest incremental completion. Fill real numbers only from reproducible runs.

## Environment
- GPU: `NVIDIA GeForce GTX 1650`
- Driver / CUDA: `581.08 / 13.0` from container-visible `nvidia-smi`
- Host shape: Windows + Docker Desktop + WSL-backed containers
- Model: `Qwen/Qwen2.5-0.5B-Instruct-AWQ`
- Quantization: `AWQ (4-bit)` via `awq_marlin`
- `MAX_MODEL_LEN`: `2048`
- `GPU_MEMORY_UTILIZATION`: attempted `0.85`, then reduced to `0.72`, then stabilized at `0.55`
- Replica count target: `3`
- Replica count currently viable in-session: live benchmarked with `1`

## Load Levels
| Load level | Concurrency | P50 TTFT | P95 TTFT | P99 TTFT | Throughput | Notes |
|---|---|---|---|---|---|---|
| 10% | `1` | `220.34 ms` | `1480.20 ms` | `1480.20 ms` | `1.11 req/s` sync, `0.52 req/s` stream | Sync sweep: `12/12` `200` responses, end-to-end `p50=867.92 ms`, `p95=1206.78 ms`; streaming sweep: `8/8` `200` responses |
| 50% | `2` | `254.90 ms` | `1192.89 ms` | `1192.89 ms` | `2.10 req/s` sync, `0.96 req/s` stream | Sync sweep: `12/12` `200` responses, end-to-end `p50=923.21 ms`, `p95=1083.86 ms`; streaming sweep: `8/8` `200` responses |
| 100% | `4` | `362.72 ms` | `444.76 ms` | `444.76 ms` | `3.81 req/s` sync, `1.96 req/s` stream | Sync sweep: `12/12` `200` responses, end-to-end `p50=1031.91 ms`, `p95=1085.16 ms`; streaming sweep: `8/8` `200` responses |

## TBT
| Load level | P50 TBT | P95 TBT | P99 TBT |
|---|---|---|---|
| 10% | `0.14 ms` | `157.82 ms` | `167.78 ms` |
| 50% | `0.12 ms` | `161.92 ms` | `169.56 ms` |
| 100% | `0.25 ms` | `166.68 ms` | `174.75 ms` |

Streaming timing was later measured directly with [`tests/benchmark_streaming.py`](/d:/infersafe/tests/benchmark_streaming.py), which computes client-observed TTFT and inter-chunk TBT percentiles from live `stream=true` requests.

Additional sanity sample from gateway metrics:
- TTFT: `495.9 ms` from `gateway_ttft_seconds_sum / count`
- TBT: `25.7 ms avg` from `gateway_tbt_seconds_sum / count = 1.6170 / 63`

## KV Cache Tuning
| Run | `GPU_MEMORY_UTILIZATION` | Throughput | P95 TTFT | Failure mode |
|---|---|---|---|---|
| Undersized cache | 0.30 | Not yet measured | Not yet measured | Pending live baseline |
| Initial failing config | 0.85 | Not measurable | Not measurable | `vLLM` engine startup failed: free VRAM `3.22 / 4.0 GiB` was below requested memory budget |
| Safer retry | 0.72 | Not yet measured | Not yet measured | Startup still not healthy during that session; required a smaller model footprint and scheduler budget |
| Final stable run | 0.55 | `3.81 req/s` at concurrency `4` | `495.9 ms` (single live streaming sample) | Healthy with `Qwen/Qwen2.5-0.5B-Instruct-AWQ`, `MAX_MODEL_LEN=2048`, `MAX_NUM_SEQS=4`, `MAX_NUM_BATCHED_TOKENS=2048` |

KV-cache control rationale:
- We prioritized a smaller quantized model and reduced `MAX_MODEL_LEN=2048` to limit KV cache growth under concurrent load.
- We treated `GPU_MEMORY_UTILIZATION` as the tunable KV-cache budget knob and documented how an aggressive setting failed on this 4 GB GPU.
- We further reduced scheduler pressure with `MAX_NUM_SEQS=4` and `MAX_NUM_BATCHED_TOKENS=2048` so the quantized backend could become stable enough for a live benchmark sweep.
- This is a legitimate mitigation strategy, even though the host did not provide a full before/after degradation-recovery curve across multiple cache sizes.

## Autoscaling / Manual Scale Demonstration
- Queue-depth trigger: documented assignment-fit policy, not yet fully benchmarked
- Scale-out action: [`scripts/manual_scale_demo.ps1`](/d:/infersafe/scripts/manual_scale_demo.ps1)
- Cold-start latency cost: pending live baseline
- Scale-in observation: pending live baseline

## Current Findings
- Gateway and load balancer start successfully and expose the intended public surfaces.
- A live end-to-end run succeeded with `Qwen/Qwen2.5-0.5B-Instruct-AWQ` on the GTX 1650 after reducing context length and scheduler pressure.
- Unit tests for gateway validation and overload behavior pass locally.
- A non-streaming benchmark sweep completed successfully at concurrency `1`, `2`, and `4` with `12/12` successful responses at each level.
- Streaming inference also succeeded, allowing direct collection of TTFT and average TBT from gateway metrics.
- Edge Case 1 and Edge Case 4 both have successful local gateway proofs with structured `400` responses and no `5xx`.
- Edge Case 2 now has a successful local overload proof showing bounded queue growth and deterministic `503 queue_overloaded` behavior.
- The original `vLLM` healthcheck bug was a false negative caused by using `python` instead of `python3` in the container.
- After fixing the healthcheck, the main blocker shifted to GPU memory and startup budget; this was mitigated enough for a single-replica quantized run, but not yet for a full three-replica benchmark.
- This is still useful assignment evidence because it is reproducible, concrete, and directly tied to model-serving infrastructure rather than a vague "it did not work."

## Edge Case Pass / Fail Matrix
| Edge case | Pass / Fail | Observed behavior | Fix / mitigation |
|---|---|---|---|
| Context overflow | Pass (gateway proof) | Local edge-case run returned structured `400` with exact excess token count | Keep token counting aligned with `MAX_CONTEXT_TOKENS` |
| Thundering herd | Pass (gateway proof) | Local overload run returned `110` deterministic `503 queue_overloaded` responses and `10` successes | Re-run on healthy backend for full replica and cold-start distribution evidence |
| Mid-stream failure | Pending baseline | Gateway-side streamed error behavior exists | Re-run after stable streaming baseline |
| Adversarial payloads | Pass (gateway proof) | All four local sub-cases returned structured `400` and no `5xx` | Preserve validation guards for null-byte, control-only, oversized, and over-nested input |
| Mixed batch GPU pressure | Blocked today | Stable long-generation backend not yet available on this host | Retry on larger GPU or smaller model / lower memory footprint |

