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
