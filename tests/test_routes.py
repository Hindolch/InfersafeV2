import json

import httpx
from fastapi.testclient import TestClient

from api.main import app, configure_runtime_state
from utils.gateway_config import GatewaySettings


def setup_gateway():
    settings = GatewaySettings(
        backend_base_url="http://upstream.test",
        max_context_tokens=64,
        max_request_bytes=2048,
        max_queue_depth=1,
        max_concurrent_requests=1,
        max_json_depth=10,
    )
    configure_runtime_state(app, settings)
    return settings


def test_health_and_ready_endpoints(monkeypatch):
    setup_gateway()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        raise AssertionError(f"Unexpected path {request.url.path}")

    monkeypatch.setattr("api.gateway_impl.build_async_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        ready = client.get("/ready")
        assert ready.status_code == 200
        assert ready.json() == {"status": "ready"}


def test_chat_completion_proxy_success(monkeypatch):
    setup_gateway()

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["messages"][0]["content"] == "hello world"
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-123",
                "object": "chat.completion",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "hi"}}],
            },
        )

    monkeypatch.setattr("api.gateway_impl.build_async_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            json={"model": "local-vllm", "messages": [{"role": "user", "content": "hello world"}], "max_tokens": 8},
        )
        assert response.status_code == 200
        assert response.json()["choices"][0]["message"]["content"] == "hi"


def test_context_overflow_returns_structured_400():
    setup_gateway()

    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "x" * 400}], "max_tokens": 64},
        )
        assert response.status_code == 400
        payload = response.json()
        assert payload["detail"]["error"]["type"] == "context_overflow"
        assert payload["detail"]["error"]["excess_tokens"] > 0


def test_queue_limit_returns_503(monkeypatch):
    settings = setup_gateway()
    app.state.queue_state.active_requests = settings.max_concurrent_requests
    app.state.queue_state.waiting_requests = settings.max_queue_depth

    monkeypatch.setattr(
        "api.gateway_impl.build_async_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"ok": True}))),
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}], "max_tokens": 4},
        )
        assert response.status_code == 503
        assert response.json()["detail"]["error"]["type"] == "queue_overloaded"
