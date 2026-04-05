import asyncio
import json
import os
from collections import Counter

from tests.edge_cases.common import build_parser, completion_payload, post_json


async def main() -> None:
    parser = build_parser("Edge Case 2: thundering herd at startup")
    parser.add_argument("--requests", type=int, default=int(os.getenv("HERD_REQUESTS", "500")))
    parser.add_argument("--max-tokens", type=int, default=32)
    parser.add_argument("--queue-depth", type=int, default=int(os.getenv("LOCAL_APP_MAX_QUEUE_DEPTH", "8")))
    parser.add_argument("--concurrency", type=int, default=int(os.getenv("LOCAL_APP_MAX_CONCURRENCY", "2")))
    parser.add_argument("--mock-upstream-delay", type=float, default=float(os.getenv("LOCAL_APP_MOCK_UPSTREAM_DELAY", "1.0")))
    args = parser.parse_args()

    if args.local_app:
        os.environ["LOCAL_APP_MAX_QUEUE_DEPTH"] = str(args.queue_depth)
        os.environ["LOCAL_APP_MAX_CONCURRENCY"] = str(args.concurrency)
        os.environ["LOCAL_APP_MOCK_UPSTREAM_DELAY"] = str(args.mock_upstream_delay)

    async def worker(index: int):
        payload = completion_payload(args.model, f"Cold start storm request {index}", max_tokens=args.max_tokens, stream=False)
        response = await post_json(args.url, payload, args.timeout, local_app=args.local_app)
        try:
            body = response.json()
        except Exception:
            body = response.text
        return {"request": index, "status": response.status_code, "body": body}

    results = await asyncio.gather(*(worker(index) for index in range(args.requests)))
    histogram = Counter(item["status"] for item in results)
    overload_count = sum(
        1 for item in results
        if item["status"] == 503 and isinstance(item["body"], dict)
        and item["body"].get("detail", {}).get("error", {}).get("type") == "queue_overloaded"
    )

    print(
        json.dumps(
            {
                "total_requests": args.requests,
                "status_histogram": dict(histogram),
                "queue_depth": args.queue_depth,
                "concurrency": args.concurrency,
                "mock_upstream_delay_seconds": args.mock_upstream_delay if args.local_app else None,
                "queue_overload_503s": overload_count,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
