import argparse
import asyncio
import os
import statistics
import time
from typing import Any

import httpx


def build_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--url", default=os.getenv("INFER_URL", "http://localhost:8000/v1/chat/completions"))
    parser.add_argument("--model", default=os.getenv("INFER_MODEL", "local-vllm"))
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--local-app", action="store_true", help="Call the local FastAPI gateway directly via ASGI instead of HTTP.")
    return parser


def completion_payload(model: str, content: Any, *, max_tokens: int, stream: bool = False) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": max_tokens,
        "stream": stream,
    }


async def post_json(url: str, payload: dict[str, Any], timeout: float, *, local_app: bool = False) -> httpx.Response:
    if local_app:
        from api.main import app
        import api.gateway_impl as gateway_impl
        from api.gateway_impl import configure_runtime_state
        from utils.gateway_config import GatewaySettings

        queue_depth = int(os.getenv("LOCAL_APP_MAX_QUEUE_DEPTH", "128"))
        concurrency = int(os.getenv("LOCAL_APP_MAX_CONCURRENCY", "32"))
        connect_timeout = float(os.getenv("LOCAL_APP_CONNECT_TIMEOUT", "10"))
        read_timeout = float(os.getenv("LOCAL_APP_READ_TIMEOUT", "300"))
        if not hasattr(app.state, "settings"):
            configure_runtime_state(
                app,
                GatewaySettings(
                    backend_base_url="http://upstream.test",
                    max_context_tokens=4096,
                    max_request_bytes=1_048_576,
                    max_queue_depth=queue_depth,
                    max_concurrent_requests=concurrency,
                    max_json_depth=50,
                    upstream_connect_timeout_seconds=connect_timeout,
                    upstream_read_timeout_seconds=read_timeout,
                ),
            )

        mock_delay = float(os.getenv("LOCAL_APP_MOCK_UPSTREAM_DELAY", "0"))
        if mock_delay > 0:
            async def handler(_: httpx.Request) -> httpx.Response:
                await asyncio.sleep(mock_delay)
                return httpx.Response(
                    200,
                    json={
                        "id": "chatcmpl-local",
                        "object": "chat.completion",
                        "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}}],
                    },
                )

            gateway_impl.build_async_client = lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=timeout)

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://local-app", timeout=timeout) as client:
            return await client.post("/v1/chat/completions", json=payload)

    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.post(url, json=payload)


def summarize_latencies(latencies: list[float]) -> dict[str, float]:
    if not latencies:
        return {"count": 0, "p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0}
    ordered = sorted(latencies)
    return {
        "count": len(ordered),
        "p50_ms": round(statistics.median(ordered) * 1000, 2),
        "p95_ms": round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))] * 1000, 2),
        "p99_ms": round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.99))] * 1000, 2),
    }


async def measure_request(url: str, payload: dict[str, Any], timeout: float, *, local_app: bool = False) -> tuple[int, float]:
    start = time.perf_counter()
    response = await post_json(url, payload, timeout, local_app=local_app)
    return response.status_code, time.perf_counter() - start
