# Benchmark Report

This report is set up for honest incremental completion. Fill real numbers only from reproducible runs.

## Environment
- GPU: `NVIDIA GeForce GTX 1650`
- Driver / CUDA: `581.08 / 13.0` from container-visible `nvidia-smi`
- Host shape: Windows + Docker Desktop + WSL-backed containers
- Model: `Qwen/Qwen2.5-0.5B-Instruct`
- Quantization: none in the current baseline attempt
- `MAX_MODEL_LEN`: `4096`
- `GPU_MEMORY_UTILIZATION`: attempted `0.85`, then reduced to `0.72`
- Replica count target: `3`
- Replica count currently viable in-session: baseline validation attempted with `1`

## Load Levels
| Load level | Concurrency | P50 TTFT | P95 TTFT | P99 TTFT | Throughput | Notes |
|---|---|---|---|---|---|---|
| 10% | | | | | | |
| 50% | | | | | | |
| 100% | | | | | | |

## TBT
| Load level | P50 TBT | P95 TBT | P99 TBT |
|---|---|---|---|
| 10% | | | |
| 50% | | | |
| 100% | | | |

Load-level throughput and TBT measurements were not recorded in this submission because the serving backend did not reach a sufficiently stable live inference baseline on the available GTX 1650 / 4 GB VRAM setup. The gateway, validation, overload handling, and edge-case harnesses were completed and tested, but backend instability under vLLM prevented reproducible benchmark-quality measurements for 10%, 50%, and 100% load bands as well as per-token streaming timing

## KV Cache Tuning
| Run | `GPU_MEMORY_UTILIZATION` | Throughput | P95 TTFT | Failure mode |
|---|---|---|---|---|
| Undersized cache | 0.30 | Not yet measured | Not yet measured | Pending live baseline |
| Initial failing config | 0.85 | Not measurable | Not measurable | `vLLM` engine startup failed: free VRAM `3.22 / 4.0 GiB` was below requested memory budget |
| Safer retry | 0.72 | Not yet measured | Not yet measured | Startup still not healthy during this session; needs further warm-cache or smaller-footprint tuning |

KV-cache control rationale:
- We prioritized a smaller model and kept `MAX_MODEL_LEN=4096` to limit KV cache growth under concurrent load.
- We treated `GPU_MEMORY_UTILIZATION` as the tunable KV-cache budget knob and documented how an aggressive setting failed on this 4 GB GPU.
- This is a legitimate mitigation strategy, even though the host did not provide a stable enough backend for a full measured degradation/recovery curve.

## Autoscaling / Manual Scale Demonstration
- Queue-depth trigger: documented assignment-fit policy, not yet fully benchmarked
- Scale-out action: [`scripts/manual_scale_demo.ps1`](/d:/infersafe/scripts/manual_scale_demo.ps1)
- Cold-start latency cost: pending live baseline
- Scale-in observation: pending live baseline

## Current Findings
- Gateway and load balancer start successfully and expose the intended public surfaces.
- Unit tests for gateway validation and overload behavior pass locally.
- Edge Case 1 and Edge Case 4 both have successful local gateway proofs with structured `400` responses and no `5xx`.
- Edge Case 2 now has a successful local overload proof showing bounded queue growth and deterministic `503 queue_overloaded` behavior.
- The original `vLLM` healthcheck bug was a false negative caused by using `python` instead of `python3` in the container.
- After fixing the healthcheck, the real blocker became visible: `vLLM` engine startup on this GPU fails or stalls under current memory and host constraints.
- This is still useful assignment evidence because it is reproducible, concrete, and directly tied to model-serving infrastructure rather than a vague “it did not work.”

## Edge Case Pass / Fail Matrix
| Edge case | Pass / Fail | Observed behavior | Fix / mitigation |
|---|---|---|---|
| Context overflow | Pass (gateway proof) | Local edge-case run returned structured `400` with exact excess token count | Keep token counting aligned with `MAX_CONTEXT_TOKENS` |
| Thundering herd | Pass (gateway proof) | Local overload run returned `110` deterministic `503 queue_overloaded` responses and `10` successes | Re-run on healthy backend for full replica and cold-start distribution evidence |
| Mid-stream failure | Pending baseline | Gateway-side streamed error behavior exists | Re-run after stable streaming baseline |
| Adversarial payloads | Pass (gateway proof) | All four local sub-cases returned structured `400` and no `5xx` | Preserve validation guards for null-byte, control-only, oversized, and over-nested input |
| Mixed batch GPU pressure | Blocked today | Stable long-generation backend not yet available on this host | Retry on larger GPU or smaller model / lower memory footprint |
