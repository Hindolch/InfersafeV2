# InfersafeV2

InfersafeV2 is a scalable LLM inference assignment submission built around a FastAPI gateway, `vLLM`, HAProxy, Prometheus, and Grafana. The repository was adapted from an earlier local inference prototype into a more assignment-aligned serving pipeline, with the final submission optimized for reproducibility, observability, and honest reporting under limited hardware.

## Submission Summary
This project targets the assignment requirements with:
- an OpenAI-compatible inference gateway
- queue-aware overload handling
- multi-replica deployment wiring
- load balancer and health-check configuration
- Prometheus/Grafana observability
- runnable edge-case scripts
- benchmark, evidence, and post-mortem documentation

The strongest completed parts are the gateway, validation, queueing behavior, observability wiring, local edge-case proofs, and a successful single-replica quantized `vLLM` run with live benchmark data. The parts that did not fully land on this machine are documented explicitly in the post-mortem rather than hidden in the README.

## End-to-End Workflow
The request path is organized as a gateway-first serving pipeline:

1. A client sends a request to `POST /v1/chat/completions`.
2. The FastAPI gateway validates request structure, size, token budget, JSON depth, and adversarial input patterns.
3. The gateway applies queue and concurrency controls.
4. The request is proxied to HAProxy.
5. HAProxy routes traffic to the configured `vLLM` replicas.
6. For streaming requests, the gateway forwards streamed chunks, records TTFT and TBT, and attempts to stop upstream work if the client disconnects.
7. Prometheus scrapes the gateway and load balancer, and Grafana provides dashboards.

This design keeps policy and resilience logic in the gateway while leaving model execution to the serving layer.

## Architecture
- `gateway`
  Implemented in [`api/gateway_impl.py`](/d:/infersafe/api/gateway_impl.py). Handles request validation, queueing, proxying, and metrics.
- `load-balancer`
  Implemented with HAProxy in [`configs/haproxy.cfg`](/d:/infersafe/configs/haproxy.cfg).
- `vllm-0`, `vllm-1`, `vllm-2`
  Defined in [`configs/docker-compose.yml`](/d:/infersafe/configs/docker-compose.yml) as the intended model-serving replicas.
- `prometheus`
  Configured in [`configs/prometheus.yml`](/d:/infersafe/configs/prometheus.yml).
- `grafana`
  Included for dashboarding and operational visibility.

## What Was Successfully Implemented
- OpenAI-compatible `POST /v1/chat/completions`
- `GET /health`, `GET /ready`, and `GET /metrics`
- structured `400` errors for context overflow and adversarial payload cases
- structured `503` errors for queue overload
- queue depth and concurrency controls in the gateway
- HAProxy load-balancer configuration and health checks
- Prometheus/Grafana wiring
- edge-case harness scripts under [`tests/edge_cases/`](/d:/infersafe/tests/edge_cases)
- benchmark, evidence, edge-case matrix, and post-mortem docs

## What Worked On This Machine
The following assignment behaviors were proven locally and are backed by captured outputs:
- Edge Case 1: context overflow
- Edge Case 2: thundering herd / overload behavior
- Edge Case 4: adversarial payloads
- healthy single-replica `vLLM` serving with `Qwen/Qwen2.5-0.5B-Instruct-AWQ`
- successful non-streaming and streaming inference through the gateway
- live TTFT, TBT, latency, and throughput measurements

Supporting evidence lives in:
- [`docs/evidence_log.md`](/d:/infersafe/docs/evidence_log.md)
- [`docs/edge_case_matrix.md`](/d:/infersafe/docs/edge_case_matrix.md)
- [`docs/benchmark_report.md`](/d:/infersafe/docs/benchmark_report.md)

Live benchmark commands used for the successful run:

```bash
venv\Scripts\python.exe -m tests.benchmark_ramp --url http://localhost:8000/v1/chat/completions --model local-vllm --levels 1,2,4 --requests 12 --max-tokens 32
venv\Scripts\python.exe -m tests.benchmark_streaming --url http://localhost:8000/v1/chat/completions --model local-vllm --levels 1,2,4 --requests 8 --max-tokens 64
```

Local validation:

```bash
venv\Scripts\python.exe -m pytest tests/test_routes.py tests/test_autoscaler.py
```

Current result: `8 passed`

## Runtime Defaults And Trade-Offs
Current default settings:
- `MODEL_NAME=Qwen/Qwen2.5-0.5B-Instruct-AWQ`
- `SERVED_MODEL_NAME=local-vllm`
- `MAX_MODEL_LEN=2048`
- `GPU_MEMORY_UTILIZATION=0.55`
- `MAX_CONTEXT_TOKENS=2048`
- `MAX_QUEUE_DEPTH=32`
- `MAX_CONCURRENT_REQUESTS=8`
- `MAX_NUM_SEQS=4`
- `MAX_NUM_BATCHED_TOKENS=2048`

These were conscious trade-offs for a constrained `4 GB` GPU:
- a smaller quantized model was chosen to reduce memory pressure
- `MAX_MODEL_LEN=2048` was used to limit KV cache growth
- `GPU_MEMORY_UTILIZATION` was reduced after a higher value failed during backend startup
- scheduler pressure was lowered with `MAX_NUM_SEQS=4` and `MAX_NUM_BATCHED_TOKENS=2048`

These choices are legitimate system-design mitigations, but they also have costs:
- lower `max_model_len` reduces usable context
- lower GPU memory utilization can reduce batching and cache headroom

## Setup
Intended full-topology command:

```bash
docker compose -f configs/docker-compose.yml up --build
```

Constrained-hardware validated path used for the successful live run on this machine:

```bash
docker compose -f configs/docker-compose.yml down
docker compose -f configs/docker-compose.yml up --build -d vllm-0 load-balancer gateway prometheus grafana
docker compose -f configs/docker-compose.yml ps
```

Default local endpoints:
- Gateway: `http://localhost:8000`
- HAProxy: `http://localhost:9000`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

## Public API
Example request:

```json
{
  "model": "local-vllm",
  "messages": [
    {"role": "user", "content": "Explain KV cache tuning."}
  ],
  "max_tokens": 256,
  "stream": false
}
```

Gateway behaviors:
- Context overflow returns `400` with `max_context_tokens`, `prompt_tokens`, `requested_tokens`, and `excess_tokens`
- Queue overload returns `503`
- Null-byte, deeply nested, and control-character-only adversarial payloads are rejected locally with structured `400`s

## Edge-Case Harness
Live-path scripts:

```bash
python -m tests.edge_cases.edge_case_1_context_overflow
python -m tests.edge_cases.edge_case_2_thundering_herd
python -m tests.edge_cases.edge_case_3_midstream_failure
python -m tests.edge_cases.edge_case_4_adversarial_payloads
python -m tests.edge_cases.edge_case_5_mixed_batch_pressure
```

Gateway-only proof mode for constrained hardware:

```bash
venv\Scripts\python.exe -m tests.edge_cases.edge_case_1_context_overflow --local-app
venv\Scripts\python.exe -m tests.edge_cases.edge_case_2_thundering_herd --local-app --requests 120 --queue-depth 8 --concurrency 2 --mock-upstream-delay 1.5
venv\Scripts\python.exe -m tests.edge_cases.edge_case_4_adversarial_payloads --local-app
```

## What Did Not Fully Meet The Assignment
The incomplete parts were the GPU-heavy end-to-end backend proofs through `vLLM`:
- a fully measured KV-cache degradation/recovery experiment with real backend throughput numbers
- a full multi-replica benchmark with all three intended `vLLM` backends healthy at once
- a complete mid-stream replica-failure proof against a healthy streaming backend
- a complete mixed-batch GPU-pressure proof under sustained long-request load

Those items are not hidden here. They are documented in detail in [`docs/postmortem.md`](/d:/infersafe/docs/postmortem.md), with supporting operational context in [`docs/benchmark_report.md`](/d:/infersafe/docs/benchmark_report.md).

## Honest Constraint Notes
Host constraints:
- GPU: `NVIDIA GeForce GTX 1650`
- VRAM: `4 GB`
- Host shape: Windows + Docker Desktop + WSL-backed containers

Observed backend reality:
- the initial `vLLM` healthcheck bug was fixed by changing `python` to `python3`
- after that fix, a real startup failure appeared at `GPU_MEMORY_UTILIZATION=0.85`
- the logged issue was insufficient free VRAM during engine initialization
- lowering the budget and switching to `Qwen/Qwen2.5-0.5B-Instruct-AWQ` with a shorter context made a single-replica live run succeed
- the remaining limit is not basic serving anymore, but scaling the same setup to the full three-replica assignment target on this hardware

## Documentation
- Benchmark report: [`docs/benchmark_report.md`](/d:/infersafe/docs/benchmark_report.md)
- Edge-case matrix: [`docs/edge_case_matrix.md`](/d:/infersafe/docs/edge_case_matrix.md)
- Evidence log: [`docs/evidence_log.md`](/d:/infersafe/docs/evidence_log.md)
- Post-mortem: [`docs/postmortem.md`](/d:/infersafe/docs/postmortem.md)

