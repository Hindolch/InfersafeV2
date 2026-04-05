from utils.gateway_config import GatewaySettings
from utils.request_validation import PayloadValidationError, validate_chat_payload


def test_request_too_large_returns_structured_error():
    settings = GatewaySettings(max_request_bytes=64)

    try:
        validate_chat_payload({"messages": [{"role": "user", "content": "x" * 200}], "max_tokens": 1}, settings)
        assert False, "Expected a PayloadValidationError"
    except PayloadValidationError as exc:
        assert exc.error_type == "request_too_large"


def test_nested_json_depth_is_rejected():
    settings = GatewaySettings(max_json_depth=3, max_request_bytes=4096)
    nested = {"a": {"b": {"c": {"d": "boom"}}}}

    try:
        validate_chat_payload({"messages": [{"role": "system", "content": nested}], "max_tokens": 8}, settings)
        assert False, "Expected a PayloadValidationError"
    except PayloadValidationError as exc:
        assert exc.error_type == "nested_json_depth_exceeded"


def test_null_bytes_only_payload_is_rejected():
    settings = GatewaySettings(max_request_bytes=4096)

    try:
        validate_chat_payload({"messages": [{"role": "user", "content": "\x00" * 32}], "max_tokens": 8}, settings)
        assert False, "Expected a PayloadValidationError"
    except PayloadValidationError as exc:
        assert exc.error_type == "null_bytes_payload"


def test_control_char_only_payload_is_rejected():
    settings = GatewaySettings(max_request_bytes=4096)
    control_only = "".join(chr(code) for code in range(0, 32))

    try:
        validate_chat_payload({"messages": [{"role": "user", "content": control_only}], "max_tokens": 8}, settings)
        assert False, "Expected a PayloadValidationError"
    except PayloadValidationError as exc:
        assert exc.error_type == "control_char_payload"
