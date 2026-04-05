import json
import math
import unicodedata
from dataclasses import dataclass
from typing import Any

from utils.gateway_config import GatewaySettings


class PayloadValidationError(Exception):
    def __init__(self, status_code: int, error_type: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type
        self.message = message
        self.details = details

    def to_response(self, request_id: str) -> dict[str, Any]:
        return {
            "error": {
                "type": self.error_type,
                "message": self.message,
                "request_id": request_id,
                **self.details,
            }
        }


@dataclass(slots=True)
class ValidationResult:
    prompt_tokens: int
    requested_tokens: int


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def _classify_text_payload(text: str) -> str | None:
    if not text:
        return None

    if all(char == "\x00" for char in text):
        return "null_bytes_only"

    non_whitespace = [char for char in text if not char.isspace()]
    if non_whitespace and all(unicodedata.category(char).startswith("C") for char in non_whitespace):
        return "control_chars_only"

    return None


def _normalize_content(content: Any, *, depth: int, max_depth: int) -> str:
    if depth > max_depth:
        raise PayloadValidationError(
            400,
            "nested_json_depth_exceeded",
            "Prompt content exceeded the maximum supported nesting depth.",
            max_allowed_depth=max_depth,
            observed_depth=depth,
        )

    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, (int, float, bool)):
        return str(content)
    if isinstance(content, list):
        return " ".join(_normalize_content(item, depth=depth + 1, max_depth=max_depth) for item in content)
    if isinstance(content, dict):
        fragments: list[str] = []
        for key, value in content.items():
            fragments.append(str(key))
            fragments.append(_normalize_content(value, depth=depth + 1, max_depth=max_depth))
        return " ".join(fragment for fragment in fragments if fragment)
    raise PayloadValidationError(400, "unsupported_content_type", f"Unsupported message content type: {type(content).__name__}")


def validate_chat_payload(payload: dict[str, Any], settings: GatewaySettings) -> tuple[dict[str, Any], ValidationResult]:
    try:
        encoded = json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise PayloadValidationError(400, "invalid_payload", str(exc)) from exc

    encoded_size = len(encoded.encode("utf-8"))
    if encoded_size > settings.max_request_bytes:
        raise PayloadValidationError(
            400,
            "request_too_large",
            "Request payload exceeds the configured maximum size.",
            max_request_bytes=settings.max_request_bytes,
            observed_request_bytes=encoded_size,
        )

    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise PayloadValidationError(400, "invalid_messages", "`messages` must be a non-empty list.")

    max_tokens = payload.get("max_tokens", 256)
    if not isinstance(max_tokens, int) or max_tokens <= 0:
        raise PayloadValidationError(400, "invalid_max_tokens", "`max_tokens` must be a positive integer.")

    normalized_messages: list[dict[str, Any]] = []
    prompt_fragments: list[str] = []
    for item in messages:
        if not isinstance(item, dict):
            raise PayloadValidationError(400, "invalid_message", "Each message must be a JSON object.")
        role = item.get("role", "user")
        content = _normalize_content(item.get("content"), depth=1, max_depth=settings.max_json_depth)
        classification = _classify_text_payload(content)
        if classification == "null_bytes_only":
            raise PayloadValidationError(
                400,
                "null_bytes_payload",
                "Prompt payload cannot consist entirely of null bytes.",
            )
        if classification == "control_chars_only":
            raise PayloadValidationError(
                400,
                "control_char_payload",
                "Prompt payload cannot consist entirely of Unicode control characters.",
            )
        prompt_fragments.append(content)
        normalized_messages.append({"role": role, "content": content})

    prompt_text = "\n".join(prompt_fragments)
    prompt_tokens = _estimate_tokens(prompt_text)
    requested_tokens = prompt_tokens + max_tokens

    if requested_tokens > settings.max_context_tokens:
        raise PayloadValidationError(
            400,
            "context_overflow",
            "Requested prompt exceeds the configured context window.",
            max_context_tokens=settings.max_context_tokens,
            prompt_tokens=prompt_tokens,
            requested_tokens=requested_tokens,
            excess_tokens=requested_tokens - settings.max_context_tokens,
        )

    normalized_payload = dict(payload)
    normalized_payload["messages"] = normalized_messages
    normalized_payload.setdefault("model", "local-vllm")
    normalized_payload["max_tokens"] = max_tokens
    normalized_payload["stream"] = bool(payload.get("stream", False))

    return normalized_payload, ValidationResult(prompt_tokens=prompt_tokens, requested_tokens=requested_tokens)
