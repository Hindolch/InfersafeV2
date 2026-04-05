import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from utils.gateway_config import GatewaySettings
from utils.request_validation import PayloadValidationError, validate_chat_payload

logger = logging.getLogger("infersafev2.gateway")

REQUEST_COUNT = Counter("gateway_requests_total", "Total number of gateway requests", ["mode", "status"])
ACTIVE_REQUESTS = Gauge("gateway_active_requests", "Current number of active upstream requests")
WAITING_REQUESTS = Gauge("gateway_waiting_requests", "Current number of queued requests")
QUEUE_REJECTIONS = Counter("gateway_queue_rejections_total", "Requests rejected because the queue was full")
INFERENCE_LATENCY = Histogram("gateway_request_duration_seconds", "End-to-end request duration")
TTFT_HISTOGRAM = Histogram("gateway_ttft_seconds", "Time to first token for streaming requests")
TBT_HISTOGRAM = Histogram("gateway_tbt_seconds", "Time between streamed chunks")
CLIENT_DISCONNECTS = Counter("gateway_client_disconnects_total", "Streaming requests aborted by the client")
UPSTREAM_DROPS = Counter("gateway_upstream_stream_drops_total", "Streaming requests dropped by upstream failures")


class QueueState:
    def __init__(self) -> None:
        self.lock = asyncio.Lock() #prevents race-conditions when multiple requests try to access the queue at the same time
        self.active_requests = 0 #number of requests currently being processed
        self.waiting_requests = 0 #number of requests waiting in the queue


def get_settings() -> GatewaySettings:
    return GatewaySettings.from_env()


def configure_runtime_state(app: FastAPI, settings: GatewaySettings | None = None) -> None:
    runtime_settings = settings or get_settings()
    app.state.settings = runtime_settings
    app.state.queue_state = QueueState()
    app.state.queue_semaphore = asyncio.Semaphore(runtime_settings.max_concurrent_requests)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not hasattr(app.state, "settings"):
        configure_runtime_state(app)
    yield


app = FastAPI(title="InfersafeV2 Gateway", version="2.0.0", lifespan=lifespan)


def build_async_client() -> httpx.AsyncClient:
    settings: GatewaySettings = app.state.settings
    timeout = httpx.Timeout(
        connect=settings.upstream_connect_timeout_seconds,
        read=settings.upstream_read_timeout_seconds,
        write=settings.upstream_connect_timeout_seconds,
        pool=settings.upstream_connect_timeout_seconds,
    )
    return httpx.AsyncClient(timeout=timeout)


async def _set_queue_metrics(state: QueueState) -> None:
    ACTIVE_REQUESTS.set(state.active_requests)
    WAITING_REQUESTS.set(state.waiting_requests)


@asynccontextmanager
async def acquire_request_slot(request_id: str):
    settings: GatewaySettings = app.state.settings
    state: QueueState = app.state.queue_state
    semaphore: asyncio.Semaphore = app.state.queue_semaphore

    async with state.lock:
        total_tracked = state.active_requests + state.waiting_requests
        if total_tracked >= settings.max_concurrent_requests + settings.max_queue_depth:
            QUEUE_REJECTIONS.inc()
            await _set_queue_metrics(state)
            raise HTTPException(
                status_code=503,
                detail={
                    "error": {
                        "type": "queue_overloaded",
                        "message": "Request queue is full. Please retry shortly.",
                        "max_concurrent_requests": settings.max_concurrent_requests,
                        "max_queue_depth": settings.max_queue_depth,
                        "current_active_requests": state.active_requests,
                        "current_waiting_requests": state.waiting_requests,
                        "request_id": request_id,
                    }
                },
            )
        state.waiting_requests += 1
        await _set_queue_metrics(state)

    try:
        await semaphore.acquire()
    except BaseException:
        async with state.lock:
            state.waiting_requests = max(0, state.waiting_requests - 1)
            await _set_queue_metrics(state)
        raise

    async with state.lock:
        state.waiting_requests = max(0, state.waiting_requests - 1)
        state.active_requests += 1
        await _set_queue_metrics(state)

    try:
        yield
    finally:
        async with state.lock:
            state.active_requests = max(0, state.active_requests - 1)
            await _set_queue_metrics(state)
        semaphore.release()


def _upstream_url(path: str) -> str:
    settings: GatewaySettings = app.state.settings
    return f"{settings.backend_base_url.rstrip('/')}{path}"


def _structured_error_event(error_type: str, message: str, request_id: str) -> bytes:
    payload = {"error": {"type": error_type, "message": message, "request_id": request_id}}
    return f"data: {json.dumps(payload)}\n\n".encode("utf-8")


@app.get("/")
async def read_root():
    return {"message": "InfersafeV2 gateway is up"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    settings: GatewaySettings = app.state.settings
    try:
        async with build_async_client() as client:
            response = await client.get(f"{settings.backend_base_url.rstrip('/')}{settings.upstream_health_path}")
        if response.status_code >= 400:
            return JSONResponse(status_code=503, content={"status": "degraded", "upstream_status": response.status_code})
        return {"status": "ready"}
    except Exception as exc:
        logger.warning("Readiness probe failed: %s", exc)
        return JSONResponse(status_code=503, content={"status": "degraded", "reason": str(exc)})


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    started = time.perf_counter()
    mode = "stream"

    try:
        payload: dict[str, Any] = await request.json()
    except json.JSONDecodeError as exc:
        REQUEST_COUNT.labels(mode="invalid", status="400").inc()
        raise HTTPException(
            status_code=400,
            detail={"error": {"type": "invalid_json", "message": str(exc), "request_id": request_id}},
        ) from exc

    try:
        settings: GatewaySettings = app.state.settings
        normalized_payload, validation = validate_chat_payload(payload, settings)
    except PayloadValidationError as exc:
        REQUEST_COUNT.labels(mode="invalid", status=str(exc.status_code)).inc()
        raise HTTPException(status_code=exc.status_code, detail=exc.to_response(request_id)) from exc

    mode = "stream" if normalized_payload.get("stream") else "sync"
    headers = {"content-type": "application/json", "x-request-id": request_id}

    async with acquire_request_slot(request_id):
        if normalized_payload.get("stream"):

            async def stream_upstream():
                first_chunk_at: float | None = None
                previous_chunk_at: float | None = None
                async with build_async_client() as client:
                    try:
                        async with client.stream(
                            "POST",
                            _upstream_url("/v1/chat/completions"),
                            json=normalized_payload,
                            headers=headers,
                        ) as upstream:
                            upstream.raise_for_status()
                            async for chunk in upstream.aiter_raw():
                                if await request.is_disconnected():
                                    CLIENT_DISCONNECTS.inc()
                                    await upstream.aclose()
                                    logger.info("Client disconnected for request_id=%s", request_id)
                                    break

                                now = time.perf_counter()
                                if first_chunk_at is None:
                                    first_chunk_at = now
                                    TTFT_HISTOGRAM.observe(first_chunk_at - started)
                                elif previous_chunk_at is not None:
                                    TBT_HISTOGRAM.observe(now - previous_chunk_at)
                                previous_chunk_at = now
                                yield chunk
                    except httpx.HTTPStatusError as exc:
                        UPSTREAM_DROPS.inc()
                        logger.error("Upstream returned %s for request_id=%s", exc.response.status_code, request_id)
                        yield _structured_error_event(
                            "upstream_http_error",
                            f"Upstream server returned status {exc.response.status_code}",
                            request_id,
                        )
                    except Exception as exc:
                        UPSTREAM_DROPS.inc()
                        logger.exception("Streaming request failed for request_id=%s", request_id)
                        yield _structured_error_event("upstream_stream_failure", str(exc), request_id)
                    finally:
                        INFERENCE_LATENCY.observe(time.perf_counter() - started)
                        REQUEST_COUNT.labels(mode=mode, status="200").inc()

            return StreamingResponse(stream_upstream(), media_type="text/event-stream")

        async with build_async_client() as client:
            try:
                response = await client.post(
                    _upstream_url("/v1/chat/completions"),
                    json=normalized_payload,
                    headers=headers,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                REQUEST_COUNT.labels(mode=mode, status=str(exc.response.status_code)).inc()
                raise HTTPException(
                    status_code=exc.response.status_code,
                    detail={"error": {"type": "upstream_http_error", "message": exc.response.text, "request_id": request_id}},
                ) from exc
            except httpx.HTTPError as exc:
                REQUEST_COUNT.labels(mode=mode, status="503").inc()
                raise HTTPException(
                    status_code=503,
                    detail={"error": {"type": "upstream_unavailable", "message": str(exc), "request_id": request_id}},
                ) from exc

        INFERENCE_LATENCY.observe(time.perf_counter() - started)
        REQUEST_COUNT.labels(mode=mode, status=str(response.status_code)).inc()
        return JSONResponse(
            status_code=response.status_code,
            content=response.json(),
            headers={
                "x-request-id": request_id,
                "x-prompt-tokens-estimate": str(validation.prompt_tokens),
                "x-requested-tokens-estimate": str(validation.requested_tokens),
            },
        )
