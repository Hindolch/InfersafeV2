# Edge Case Matrix

This file is the submission tracking for the current machine. 

| Edge case | Current status | Evidence path | Observed behavior | Fix / mitigation |
|---|---|---|---|---|
| Context overflow | Pass at gateway layer | `tests/edge_cases/edge_case_1_context_overflow.py --local-app` | Returned `400` with `prompt_tokens=12500`, `requested_tokens=13524`, and `excess_tokens=9428` | Keep token counting and `MAX_CONTEXT_TOKENS` aligned with `MAX_MODEL_LEN` |
| Thundering herd | Pass at gateway layer | `tests/edge_cases/edge_case_2_thundering_herd.py --local-app --requests 120 --queue-depth 8 --concurrency 2 --mock-upstream-delay 1.5` | Returned `110` deterministic `503 queue_overloaded` responses and `10` successful responses under forced cold-start pressure | Use queue caps and backpressure to avoid unbounded growth; repeat on healthy backend for full replica-distribution evidence |
| Mid-stream failure | Partial, baseline now available | `tests/edge_cases/edge_case_3_midstream_failure.py` | Gateway has terminal streamed error handling and a healthy single-replica streaming baseline now exists; replica-kill proof still not captured | Run against the live baseline, then kill one replica and capture dropped request count |
| Adversarial payloads | Pass at gateway layer | `tests/edge_cases/edge_case_4_adversarial_payloads.py --local-app` | All four sub-cases returned structured `400` responses and no `5xx` | Preserve local validation for null-byte, control-only, oversized, and over-nested inputs |
| Mixed batch GPU pressure | Pending further live run | `tests/edge_cases/edge_case_5_mixed_batch_pressure.py` | Single-replica live serving now works, but sustained long-form pressure and short-request starvation have not yet been measured | Retry on this tuned baseline first, then move to a larger GPU host if the GTX 1650 cannot hold the longer pressure run |
