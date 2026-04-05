# Post-Mortem

## Failure which caught my eye
The most surprising failure was that the stack looked superficially alive while no model replica was actually healthy. The gateway, HAProxy, Prometheus, and Grafana all started cleanly, so the system initially appeared close to done. The real failure only surfaced after drilling into the `vLLM` container health and engine logs.

## What I Expected
I expected the smallest practical `vLLM` baseline model, `Qwen/Qwen2.5-0.5B-Instruct`, to start on a GTX 1650 once the gateway and Compose wiring were correct. My working assumption was that most remaining issues would be around proxying, streaming, or health-check plumbing rather than model engine startup.

## What Actually Happened
Two different failures happened in sequence:

1. The initial replica health checks were false negatives because the container health probe used `python` while the image only exposed `python3`.
2. After fixing that, the real engine error appeared: `vLLM` startup failed because the configured `gpu_memory_utilization=0.85` exceeded the free VRAM available on startup. The engine log showed only `3.22 / 4.0 GiB` free, below the requested target of `3.4 GiB`.

Lowering the memory target removed that exact error, but the model server still did not become healthy within the session window, which suggests a second-order startup or host-constraint issue still needs to be resolved.

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
- Lowered the default `GPU_MEMORY_UTILIZATION` from `0.85` to `0.72`.
- Reduced the default model target to a smaller baseline model more appropriate for a 4 GB GPU.
- Added gateway-side protections and reproducible edge-case scripts so progress is still measurable even while the backend is constrained.

The likely next fixes if more time were available:

- Warm the model cache explicitly before booting replicas.
- Try an even smaller model footprint or lower context length.
- Validate whether a different `vLLM` version or startup mode behaves better on this GPU / WSL combination.

## What Still Did Not Fully Work
The following assignment targets remained incomplete on this machine:

- a stable healthy `vLLM` inference baseline through the full Docker path
- a measured KV-cache degradation and recovery experiment with real backend throughput numbers
- full mid-stream replica-failure proof against a healthy streaming backend
- full mixed-batch GPU-pressure proof under sustained long-request load

These are intentionally preserved as unresolved items in the submission. They were not removed from the write-up because the assignment explicitly mentioned it values honest failure analysis over unsupported claims.

## A few things which could be instrumented differently! 
If starting over, I would instrument the serving layer earlier and more aggressively:

- Capture `vLLM` engine startup logs separately from container health logs.
- Add a startup script that verifies GPU free memory before launching the engine.
- Stage the assignment exactly as the prompt suggests: single healthy replica first, then load balancer, then scaling, then edge-case chaos.
- Pre-download model weights before bringing up multiple replicas to avoid noisy warm-cache behavior.

The main lesson is that reproducibility and honest failure analysis are not a fallback they are part of the deliverable. On this machine, that honesty is what keeps the submission credible and still competitive.
