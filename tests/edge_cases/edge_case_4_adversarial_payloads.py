import asyncio
import base64
import json

from tests.edge_cases.common import build_parser, completion_payload, post_json


def nested_payload(depth: int) -> dict:
    root: dict = {"leaf": "value"}
    for index in range(depth):
        root = {"level": index, "child": root}
    return root


async def main() -> None:
    parser = build_parser("Edge Case 4: adversarial input payloads")
    args = parser.parse_args()

    cases = {
        "null_bytes": completion_payload(args.model, "\x00" * 256, max_tokens=8),
        "large_base64": completion_payload(args.model, base64.b64encode(b"x" * 750000).decode("ascii"), max_tokens=8),
        "nested_json": {
            "model": args.model,
            "messages": [{"role": "system", "content": nested_payload(55)}, {"role": "user", "content": "hello"}],
            "max_tokens": 8,
        },
        "control_chars": completion_payload(args.model, "".join(chr(code) for code in range(0, 32)), max_tokens=8),
    }

    results = {}
    for name, payload in cases.items():
        response = await post_json(args.url, payload, args.timeout, local_app=args.local_app)
        try:
            body = response.json()
        except Exception:
            body = response.text
        results[name] = {"status_code": response.status_code, "body": body}

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
