import os
from dataclasses import dataclass


@dataclass(slots=True)
class GatewaySettings:
    backend_base_url: str = "http://load-balancer:9000"
    upstream_health_path: str = "/health"
    max_context_tokens: int = 4096
    max_request_bytes: int = 1_048_576
    max_queue_depth: int = 128
    max_concurrent_requests: int = 32
    max_json_depth: int = 50
    upstream_connect_timeout_seconds: float = 10.0
    upstream_read_timeout_seconds: float = 300.0

    @classmethod
    def from_env(cls) -> "GatewaySettings":
        defaults = cls()
        return cls(
            backend_base_url=os.getenv("BACKEND_BASE_URL", defaults.backend_base_url),
            upstream_health_path=os.getenv("UPSTREAM_HEALTH_PATH", defaults.upstream_health_path),
            max_context_tokens=int(os.getenv("MAX_CONTEXT_TOKENS", str(defaults.max_context_tokens))),
            max_request_bytes=int(os.getenv("MAX_REQUEST_BYTES", str(defaults.max_request_bytes))),
            max_queue_depth=int(os.getenv("MAX_QUEUE_DEPTH", str(defaults.max_queue_depth))),
            max_concurrent_requests=int(os.getenv("MAX_CONCURRENT_REQUESTS", str(defaults.max_concurrent_requests))),
            max_json_depth=int(os.getenv("MAX_JSON_DEPTH", str(defaults.max_json_depth))),
            upstream_connect_timeout_seconds=float(
                os.getenv("UPSTREAM_CONNECT_TIMEOUT_SECONDS", str(defaults.upstream_connect_timeout_seconds))
            ),
            upstream_read_timeout_seconds=float(
                os.getenv("UPSTREAM_READ_TIMEOUT_SECONDS", str(defaults.upstream_read_timeout_seconds))
            ),
        )
