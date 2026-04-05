# Evidence Log

This file captures concrete outputs gathered during the final repo pass.

## Local Validation
- `venv\Scripts\python.exe -m pytest tests/test_routes.py tests/test_autoscaler.py`
- Result: `8 passed`

## Edge Case 1: Context Overflow
Command:

```bash
venv\Scripts\python.exe -m tests.edge_cases.edge_case_1_context_overflow --local-app
```

Observed result:

```json
{
  "status_code": 400,
  "body": {
    "detail": {
      "error": {
        "type": "context_overflow",
        "max_context_tokens": 4096,
        "prompt_tokens": 12500,
        "requested_tokens": 13524,
        "excess_tokens": 9428
      }
    }
  }
}
```

## Edge Case 4: Adversarial Payloads
Command:

```bash
venv\Scripts\python.exe -m tests.edge_cases.edge_case_4_adversarial_payloads --local-app
```

Observed result summary:
- `null_bytes` -> `400` `null_bytes_payload`
- `large_base64` -> `400` `context_overflow`
- `nested_json` -> `400` `nested_json_depth_exceeded`
- `control_chars` -> `400` `control_char_payload`

No sub-case returned `5xx`.

## Edge Case 2: Thundering Herd
Command:

```bash
venv\Scripts\python.exe -m tests.edge_cases.edge_case_2_thundering_herd --local-app --requests 120 --queue-depth 8 --concurrency 2 --mock-upstream-delay 1.5
```

Observed result:

```json
{
  "total_requests": 120,
  "status_histogram": {
    "200": 10,
    "503": 110
  },
  "queue_depth": 8,
  "concurrency": 2,
  "mock_upstream_delay_seconds": 1.5,
  "queue_overload_503s": 110
}
```

This demonstrates bounded queue growth and deterministic overload behavior rather than timeout cascade or silent hangs.

## Live Single-Replica Quantized Serving
Runtime shape:
- Model: `Qwen/Qwen2.5-0.5B-Instruct-AWQ`
- `MAX_MODEL_LEN=2048`
- `GPU_MEMORY_UTILIZATION=0.55`
- `MAX_NUM_SEQS=4`
- `MAX_NUM_BATCHED_TOKENS=2048`

Observed runtime milestones:
- `docker compose -f configs/docker-compose.yml ps` showed `infersafev2-vllm-0` up and serving behind the gateway stack
- `curl.exe http://localhost:8000/health` returned `{"status":"ok"}`
- `curl.exe http://localhost:8000/ready` returned `{"status":"ready"}`

Non-streaming inference proof:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/v1/chat/completions" -Method Post -ContentType "application/json" -Body (@{model="local-vllm";messages=@(@{role="user";content="Say hello in one short sentence."});max_tokens=32;stream=$false} | ConvertTo-Json -Depth 5)
```

Observed result summary:
- `object=chat.completion`
- `model=local-vllm`
- `usage.prompt_tokens=36`
- `usage.completion_tokens=10`
- `finish_reason=stop`

Streaming inference proof:

```powershell
Invoke-WebRequest -Uri "http://localhost:8000/v1/chat/completions" -Method Post -ContentType "application/json" -Body (@{model="local-vllm";messages=@(@{role="user";content="Explain KV cache in two short points."});max_tokens=64;stream=$true} | ConvertTo-Json -Depth 5) -UseBasicParsing
```

Observed result summary:
- `StatusCode=200`
- `Content-Type=text/event-stream`
- streamed chunks returned successfully end to end

Gateway metrics sample after live requests:
- `gateway_ttft_seconds_sum=0.4959`
- `gateway_ttft_seconds_count=1`
- `gateway_tbt_seconds_sum=1.6170`
- `gateway_tbt_seconds_count=63`
- `gateway_request_duration_seconds_sum=12.7637`
- `gateway_request_duration_seconds_count=4`

## Non-Streaming Benchmark Sweep
Command:

```bash
venv\Scripts\python.exe -m tests.benchmark_ramp --url http://localhost:8000/v1/chat/completions --model local-vllm --levels 1,2,4 --requests 12 --max-tokens 32
```

Observed result:

```json
[
  {
    "concurrency": 1,
    "total_requests": 12,
    "duration_seconds": 10.76,
    "throughput_rps": 1.11,
    "p50_ms": 867.92,
    "p95_ms": 1206.78,
    "p99_ms": 1206.78,
    "status_histogram": {
      "200": 12
    }
  },
  {
    "concurrency": 2,
    "total_requests": 12,
    "duration_seconds": 5.7,
    "throughput_rps": 2.1,
    "p50_ms": 923.21,
    "p95_ms": 1083.86,
    "p99_ms": 1083.86,
    "status_histogram": {
      "200": 12
    }
  },
  {
    "concurrency": 4,
    "total_requests": 12,
    "duration_seconds": 3.15,
    "throughput_rps": 3.81,
    "p50_ms": 1031.91,
    "p95_ms": 1085.16,
    "p99_ms": 1085.16,
    "status_histogram": {
      "200": 12
    }
  }
]
```

## Streaming Benchmark Sweep
Command:

```bash
venv\Scripts\python.exe -m tests.benchmark_streaming --url http://localhost:8000/v1/chat/completions --model local-vllm --levels 1,2,4 --requests 8 --max-tokens 64
```

Observed result:

```json
[
  {
    "concurrency": 1,
    "total_requests": 8,
    "duration_seconds": 15.44,
    "throughput_rps": 0.52,
    "status_histogram": {
      "200": 8
    },
    "ttft_p50_ms": 220.34,
    "ttft_p95_ms": 1480.2,
    "ttft_p99_ms": 1480.2,
    "tbt_p50_ms": 0.14,
    "tbt_p95_ms": 157.82,
    "tbt_p99_ms": 167.78,
    "tbt_sample_count": 505,
    "avg_chunks_per_request": 64.12
  },
  {
    "concurrency": 2,
    "total_requests": 8,
    "duration_seconds": 8.32,
    "throughput_rps": 0.96,
    "status_histogram": {
      "200": 8
    },
    "ttft_p50_ms": 254.9,
    "ttft_p95_ms": 1192.89,
    "ttft_p99_ms": 1192.89,
    "tbt_p50_ms": 0.12,
    "tbt_p95_ms": 161.92,
    "tbt_p99_ms": 169.56,
    "tbt_sample_count": 504,
    "avg_chunks_per_request": 64.0
  },
  {
    "concurrency": 4,
    "total_requests": 8,
    "duration_seconds": 4.07,
    "throughput_rps": 1.96,
    "status_histogram": {
      "200": 8
    },
    "ttft_p50_ms": 362.72,
    "ttft_p95_ms": 444.76,
    "ttft_p99_ms": 444.76,
    "tbt_p50_ms": 0.25,
    "tbt_p95_ms": 166.68,
    "tbt_p99_ms": 174.75,
    "tbt_sample_count": 504,
    "avg_chunks_per_request": 64.0
  }
]
```
