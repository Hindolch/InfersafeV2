# Post-Mortem

## Failure which caught my eye
The most surprising failure was that the stack looked superficially alive while no model replica was actually healthy. The gateway, HAProxy, Prometheus, and Grafana all started cleanly, so the system initially appeared close to done. The real failure only surfaced after drilling into the `vLLM` container health and engine logs.

## What I Expected
I expected the smallest practical `vLLM` baseline model to start on a GTX 1650 once the gateway and Compose wiring were correct. My working assumption was that most remaining issues would be around proxying, streaming, or health-check plumbing rather than model engine startup.

## What Actually Happened
Two different failures happened in sequence before the system became stable enough for a live single-replica run:

1. The initial replica health checks were false negatives because the container health probe used `python` while the image only exposed `python3`.
2. After fixing that, the real engine error appeared: `vLLM` startup failed because the configured `gpu_memory_utilization=0.85` exceeded the free VRAM available on startup. The engine log showed only `3.22 / 4.0 GiB` free, below the requested target of `3.4 GiB`.

Lowering the memory target removed that exact error, but the model server still did not become healthy until the serving profile was reduced further. The eventual successful run used `Qwen/Qwen2.5-0.5B-Instruct-AWQ`, `MAX_MODEL_LEN=2048`, `GPU_MEMORY_UTILIZATION=0.55`, `MAX_NUM_SEQS=4`, and `MAX_NUM_BATCHED_TOKENS=2048`.

## Root Cause
The root cause was not a single bug. It was a stack of system realities:

- Windows + Docker Desktop + WSL added extra complexity to process startup and multiprocessing behavior.
- The host GPU has only 4 GB of VRAM, leaving very little safety margin for `vLLM`.
- The first visible failure was masked by a bad healthcheck command.
- Once the false health signal was removed, the real VRAM constraint became visible.

This is exactly the kind of layered infrastructure problem the assignment is trying to surface: the first thing that looks broken is not always the thing that is actually blocking you.

## Fix
The fixes completed so far:

- Replaced the healthcheck command from `python` to `python3` in the `vLLM` services.
- Lowered the default `GPU_MEMORY_UTILIZATION` from `0.85` to `0.72`, then to a stable `0.55`.
- Switched the default serving target to `Qwen/Qwen2.5-0.5B-Instruct-AWQ`.
- Reduced `MAX_MODEL_LEN` to `2048`.
- Lowered scheduler pressure with `MAX_NUM_SEQS=4` and `MAX_NUM_BATCHED_TOKENS=2048`.
- Added gateway-side protections and reproducible edge-case scripts so progress is still measurable even while the backend is constrained.

The likely next fixes if more time were available:

- Warm the model cache explicitly before booting replicas.
- Try replica-by-replica scaling after the single-replica baseline instead of aiming at the full topology immediately.
- Validate whether a different `vLLM` version or startup mode behaves better on this GPU / WSL combination.

## What Still Did Not Fully Work
The following assignment targets remained incomplete on this machine:

- a measured KV-cache degradation and recovery experiment with real backend throughput numbers
- a stable three-replica benchmark path with all intended backends healthy at once
- full mid-stream replica-failure proof against a healthy streaming backend
- full mixed-batch GPU-pressure proof under sustained long-request load

These are intentionally preserved as unresolved items in the submission. They were not removed from the write-up because the assignment explicitly mentioned it values honest failure analysis over unsupported claims.

## What I Would Instrument Or Architect Differently
If restarting this project from scratch, I would make the serving layer easier to debug before adding scale or chaos:

- Capture `vLLM` engine startup logs separately from container health logs so a failed readiness check can be traced back to the actual engine cause.
- Add a startup preflight that checks free GPU memory before launching the engine, so impossible memory budgets fail fast with a clear message.
- Build the stack in strict stages: single healthy replica first, then load balancer, then scaling, then edge-case failure injection.
- Pre-download model weights before bringing up replicas so model acquisition does not get mixed into startup, health, and benchmark timing.

The main lesson is that reproducibility and honest failure analysis are not fallback work. They are part of the deliverable. On this machine, that discipline is what kept the submission credible while still allowing a real, benchmarked serving path to emerge.
