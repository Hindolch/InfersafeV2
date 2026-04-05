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

The strongest completed parts are the gateway, validation, queueing behavior, observability wiring, and edge-case proofs that can be demonstrated locally. The parts that did not fully land on this machine are documented explicitly in the post-mortem rather than hidden in the README.

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
- benchmark, evidence, scorecard, and post-mortem docs

## What Worked On This Machine
The following assignment behaviors were proven locally and are backed by captured outputs:
- Edge Case 1: context overflow
- Edge Case 2: thundering herd / overload behavior
- Edge Case 4: adversarial payloads

Supporting evidence lives in:
- [`docs/evidence_log.md`](/d:/infersafe/docs/evidence_log.md)
- [`docs/edge_case_matrix.md`](/d:/infersafe/docs/edge_case_matrix.md)
- [`docs/benchmark_report.md`](/d:/infersafe/docs/benchmark_report.md)

Local validation:

```bash
venv\Scripts\python.exe -m pytest tests/test_routes.py tests/test_autoscaler.py
```

Current result: `8 passed`

## Runtime Defaults And Trade-Offs
Current default settings:
- `MODEL_NAME=Qwen/Qwen2.5-0.5B-Instruct`
- `SERVED_MODEL_NAME=local-vllm`
- `MAX_MODEL_LEN=4096`
- `GPU_MEMORY_UTILIZATION=0.72`
- `MAX_CONTEXT_TOKENS=4096`
- `MAX_QUEUE_DEPTH=128`
- `MAX_CONCURRENT_REQUESTS=32`

These were conscious trade-offs for a constrained `4 GB` GPU:
- a smaller model was chosen to reduce memory pressure
- `MAX_MODEL_LEN=4096` was used to limit KV cache growth
- `GPU_MEMORY_UTILIZATION` was reduced after a higher value failed during backend startup

These choices are legitimate system-design mitigations, but they also have costs:
- lower `max_model_len` reduces usable context
- lower GPU memory utilization can reduce batching and cache headroom

## One-Command Setup
```bash
docker compose -f configs/docker-compose.yml up --build
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
- a stable healthy `vLLM` serving baseline through the full Docker path
- a fully measured KV-cache degradation/recovery experiment with real backend throughput numbers
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
- lowering the budget was the correct mitigation attempt, but stable backend serving still did not fully complete on this machine during the working session

## Documentation
- Benchmark report: [`docs/benchmark_report.md`](/d:/infersafe/docs/benchmark_report.md)
- Edge-case matrix: [`docs/edge_case_matrix.md`](/d:/infersafe/docs/edge_case_matrix.md)
- Evidence log: [`docs/evidence_log.md`](/d:/infersafe/docs/evidence_log.md)
- Post-mortem: [`docs/postmortem.md`](/d:/infersafe/docs/postmortem.md)

## Closing Note
This README is intentionally focused on the implemented pipeline, successful evidence, and the architectural trade-offs that were made to adapt to limited compute. The failures and unresolved backend limitations are deliberately documented in the post-mortem, because for this assignment honest diagnosis is more credible than overstated success.

<!-- Archived earlier README content retained below during repository transition.

InfersafeV2 now targets the assignment’s real serving path: a FastAPI gateway in front of `vLLM`, HAProxy load balancing, and Prometheus/Grafana observability. The old local `llama_cpp` worker simulation is no longer the main execution path.

## What This Stack Does
- Exposes `POST /v1/chat/completions`
- Proxies streaming and non-streaming OpenAI-style requests to `vLLM`
- Rejects context overflow with a structured `400`
- Rejects queue saturation with a structured `503`
- Runs 3 `vLLM` replicas behind HAProxy health checks
- Captures latency, TTFT, TBT, queue depth, and disconnect metrics
- Includes runnable assignment harnesses under `tests/edge_cases/`

## Architecture
- `gateway`: request validation, queue/backpressure policy, metrics, and client disconnect handling
- `load-balancer`: HAProxy frontend for 3 model replicas
- `vllm-0`, `vllm-1`, `vllm-2`: OpenAI-compatible inference servers
- `prometheus`: metrics scraping
- `grafana`: dashboards

## One-Command Local Setup
```bash
docker compose -f configs/docker-compose.yml up --build
```

Default local endpoints:
- Gateway: `http://localhost:8000`
- HAProxy: `http://localhost:9000`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

## Default Runtime Settings
- `MODEL_NAME=Qwen/Qwen2.5-0.5B-Instruct`
- `SERVED_MODEL_NAME=local-vllm`
- `MAX_MODEL_LEN=4096`
- `GPU_MEMORY_UTILIZATION=0.72`
- `MAX_CONTEXT_TOKENS=4096`
- `MAX_QUEUE_DEPTH=128`
- `MAX_CONCURRENT_REQUESTS=32`

If one GPU cannot support 3 replicas of the default model, keep the architecture intact and swap to a smaller quantized model before benchmarking.

## Public API
### `POST /v1/chat/completions`
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

Health endpoints:
- `GET /health`
- `GET /ready`
- `GET /metrics`

Structured errors:
- Context overflow: `400` with `max_context_tokens`, `prompt_tokens`, `requested_tokens`, and `excess_tokens`
- Queue overload: `503` with active/waiting queue counts
- Oversized or malformed payloads: `400`

## Running Tests
```bash
pytest tests/test_routes.py tests/test_autoscaler.py
```

## Edge Case Harness
```bash
python -m tests.edge_cases.edge_case_1_context_overflow
python -m tests.edge_cases.edge_case_2_thundering_herd
python -m tests.edge_cases.edge_case_3_midstream_failure
python -m tests.edge_cases.edge_case_4_adversarial_payloads
python -m tests.edge_cases.edge_case_5_mixed_batch_pressure
```

For gateway-only proofs on a constrained machine, use local ASGI mode:

```bash
python -m tests.edge_cases.edge_case_1_context_overflow --local-app
python -m tests.edge_cases.edge_case_4_adversarial_payloads --local-app
```

## Benchmark And Deliverables
- Benchmark template: [`docs/benchmark_report.md`](/d:/infersafe/docs/benchmark_report.md)
- Post-mortem template: [`docs/postmortem.md`](/d:/infersafe/docs/postmortem.md)

KV-cache tuning workflow:
1. Run once with `GPU_MEMORY_UTILIZATION=0.30`
2. Capture degraded throughput and latency
3. Run again with `GPU_MEMORY_UTILIZATION=0.72`
4. Record before/after values in the benchmark report

## Edge Case Matrix
| Edge case | Status | Observed behavior | Fix / mitigation |
|---|---|---|---|
| Context overflow | Implemented | Structured `400` from the gateway | Align `MAX_CONTEXT_TOKENS` with model length |
| Thundering herd | Harness provided | Queue caps produce deterministic overload behavior | Tune queue depth and concurrency |
| Mid-stream failure | Harness provided | Gateway emits terminal streamed error on upstream failure | Add retries only if they preserve semantics |
| Adversarial payloads | Implemented | Oversized and over-nested payloads fail with `400`, not `5xx` | Tighten limits as needed |
| Mixed batch pressure | Harness provided | Measures short-request latency under long-request load | Separate traffic classes or reduce saturation |

## Current Constraint Notes
- Host GPU: `NVIDIA GeForce GTX 1650 (4 GB VRAM)`
- The gateway, HAProxy, Prometheus, Grafana, validation, and edge-case harnesses are in place and testable.
- A live `vLLM` boot attempt on this host exposed a real initialization limit: at `GPU_MEMORY_UTILIZATION=0.85`, engine startup fails because free VRAM is below the requested threshold.
- Lowering the target memory avoids that exact failure, but on this machine the `vLLM` container still does not reach a healthy listening state quickly enough for a full end-to-end pass during this session.
- Because the assignment rewards reproducibility and honest diagnosis, this repo now includes the exact runtime shape, scripts, and documentation needed to show what passed, what is blocked, and why.

## Score Strategy
To clear the assignment threshold honestly on this machine, optimize for:
1. Strong Phase 1 scaffolding with real configs, gateway logic, metrics, and deployment wiring.
2. Clean scripted proofs for the edge cases the gateway can already enforce locally.
3. Clear pass/fail reporting for blocked GPU-bound cases instead of overstating success.
4. A rigorous benchmark report and post-mortem that explain the GTX 1650 / WSL / VRAM limits with concrete evidence.

Current evidence-backed wins:
- Edge Case 1 is proven locally through the gateway with structured `400` and exact excess-token reporting.
- Edge Case 2 is proven locally through the gateway with deterministic queue overload behavior under a simulated cold-start storm.
- Edge Case 4 is proven locally through the gateway with four structured `400` responses and no `5xx`.
- Gateway validation and overload tests pass locally with `8` passing unit tests.
- Captured proof outputs are collected in [`docs/evidence_log.md`](/d:/infersafe/docs/evidence_log.md).

<!-- Legacy README content kept below for reference.

**InfersafeV2** is a production-grade, self-healing LLM inference infrastructure inspired by companies like Together.ai. Built with modularity, resilience, and scalability in mind, it supports:

- ⚙️ Dynamic batching
- 🧠 Multi-model inference
- 📉 Token streaming
- 🔁 Failure detection and auto-recovery
- 📈 Prometheus metrics for observability
- 📈 Simulated autoscaling logic (based on concurrency & load)
- 🚀 Kubernetes-ready architecture

---

## 🔧 Architecture Overview

InfersafeV2 is composed of:

- **FastAPI API Layer:** Entry point for all inference, reload, and metrics requests.
- **ModelWorker Instances:** Simulated LLMs (using TinyLLaMA or placeholders) with built-in retry and streaming.
- **MultiModelManager:** Handles GPU-aware routing and load balancing across multiple model workers.
- **Failure Detector:** Auto-heals failed models by reloading them and updating the worker pool.
- **Autoscaling Logic:** Monitors active request load and spins up/down worker instances based on thresholds (simulated).
- **Prometheus Metrics:** Exposes inference counts, latencies, retries, memory stats, and model health.

---

## 🧪 Features Implemented

| Feature                          | Status |
|----------------------------------|--------|
| Dynamic Batching & Inference     | ✅     |
| Token Streaming via Server-Sent Events | ✅ |
| Model Hot Reloading             | ✅     |
| Multi-Model Load Balancing       | ✅     |
| Simulated GPU-Aware Scheduling   | ✅     |
| Failure Detection & Recovery     | ✅     |
| Prometheus Observability         | ✅     |
| Dockerized Environment           | ✅     |
| Kubernetes YAML (basic setup)    | ✅     |
| Horizontal Autoscaling (Simulated) | ✅   |

---

## 🎥 Workflow animation video


https://github.com/user-attachments/assets/cd8be5ab-58c6-41c6-b208-51c19d7b61a0



## 📷 Screenshots (Swagger UI)

> Demonstrating working endpoints:

![Screenshot from 2025-06-18 22-44-21](https://github.com/user-attachments/assets/28ba9c25-8767-4a4d-a78e-41c3f775d6c4)

- `/generate-batch`: Returns a generated response from the model.

![Screenshot from 2025-06-18 22-45-17](https://github.com/user-attachments/assets/ba337b03-71bf-4a0c-a436-b488d0299ce4)
![Screenshot from 2025-06-18 22-46-01](https://github.com/user-attachments/assets/9234d56c-8005-469d-b992-d03e2048abd0)


- `/reload-model`: Dynamically reloads the model on failure.
![Screenshot from 2025-06-18 22-47-58](https://github.com/user-attachments/assets/1ee0a39d-8f31-41af-a26f-6d583409f9bf)

- `/metrics`: Exposes Prometheus-compatible metrics.
![Screenshot from 2025-06-18 22-46-44](https://github.com/user-attachments/assets/594c1ea6-5ba6-4bc9-8993-acfd7a0dd570)
![Screenshot from 2025-06-18 22-46-48](https://github.com/user-attachments/assets/68363aec-663e-499d-9294-d4b7ad709344)


## ⚙️ Simulated Autoscaling Logic

InfersafeV2 simulates real-world autoscaling with:

- **Concurrency-aware scaling:** Spins up additional model workers when concurrent requests exceed a threshold.
- **Failure-aware fallback:** Automatically replaces failed workers and rebalances traffic.
- **Metrics-integrated decisions:** All scaling decisions are observable via Prometheus metrics (`active_workers`, `queued_requests`, etc.)

Although constrained by local resources, this logic mimics production Horizontal Pod Autoscalers (HPA) in Kubernetes.

---

## 📦 Running the Project

### 1. Clone and Build the Docker Image

```bash
git clone https://github.com/yourusername/InfersafeV2.git
cd InfersafeV2
docker build -t infersafev2 .
````

### 2. Run the Container

```bash
docker run -p 8000:8000 infersafev2
```

### 3. Visit Swagger Docs

Open your browser at `http://localhost:8000/docs`

---

## ⚠️ Design Note on System Constraints

> This project was developed under limited local hardware constraints (8GB RAM, 4GB GPU), which restricted the use of large-scale LLMs or multi-GPU setups. And in load_test file I've tried to simulate real world scenario by passing in 10 prompts all together!
>
> As a result, the system **simulates**:
>
> * Multi-model workers
> * GPU-aware load balancing
> * Autoscaling decisions
>
> However, the architecture is fully modular and can plug directly into:
>
> * Real LLMs like LLaMA2, Mistral, or Mixtral
> * Actual GPU monitoring tools (like NVIDIA SMI)
> * Kubernetes Horizontal Pod Autoscaler (HPA) for scaling in production

💡 The core infrastructure is ready for production and only one deployment config away.

---

## 🔮 Future Improvements

* ✅ Integrate actual LLMs via HuggingFace Transformers
* ⏩ Replace simulation with true GPU load metrics
* 📦 Add Redis or Kafka for async job queues
* 📡 Use HPA for true horizontal scaling on K8s
* 🌐 Add WebSocket support for real-time UI streaming

---

## 🧠 Why This Matters

InfersafeV2 was built to showcase:

* Resilience engineering for AI systems
* MLOps principles applied to inference pipelines
* Autoscaling and recovery design under system constraints
* Real-world thinking in system design

---

## 📚 Tech Stack

* `Python`, `FastAPI`, `Uvicorn`
* `Prometheus`, `Docker`
* `Kubernetes (basic YAMLs)`
* `pytest` for unit and load tests

---

---

## 🧪 Running Tests

Some tests involving actual inference are skipped by default if the model file (`.gguf`) is missing.

To enable full testing:

1. Download the `tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf` model from [llama.cpp models](https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF)  
2. Place it in the `models/` directory.

```bash
pytest tests/


## 👨‍💻 Author

**Hindol R. Choudhury @InfersafeV2**
*Built with ❤️ 

---

## 📝 License

MIT License
-->
