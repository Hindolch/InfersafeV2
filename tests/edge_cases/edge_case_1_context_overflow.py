import asyncio
import json
import os

from tests.edge_cases.common import build_parser, completion_payload, post_json


async def main() -> None:
    parser = build_parser("Edge Case 1: maximum context overflow")
    parser.add_argument("--prompt-bytes", type=int, default=int(os.getenv("OVERFLOW_PROMPT_BYTES", "50000")))
    parser.add_argument("--max-tokens", type=int, default=1024)
    args = parser.parse_args()

    payload = completion_payload(args.model, "x" * args.prompt_bytes, max_tokens=args.max_tokens, stream=False)
    response = await post_json(args.url, payload, args.timeout, local_app=args.local_app)
    print(json.dumps({"status_code": response.status_code, "body": response.json()}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
