import asyncio
import json

from tests.edge_cases.common import build_parser, completion_payload, measure_request, summarize_latencies


async def main() -> None:
    parser = build_parser("Edge Case 5: GPU memory pressure under mixed batch sizes")
    parser.add_argument("--long-requests", type=int, default=8)
    parser.add_argument("--short-requests", type=int, default=50)
    parser.add_argument("--long-max-tokens", type=int, default=8192)
    parser.add_argument("--short-max-tokens", type=int, default=1)
    args = parser.parse_args()

    long_payload = completion_payload(args.model, "Write a very long story about distributed inference systems.", max_tokens=args.long_max_tokens)
    short_payload = completion_payload(args.model, "ping", max_tokens=args.short_max_tokens)

    async def long_runner() -> tuple[int, float]:
        return await measure_request(args.url, long_payload, args.timeout, local_app=args.local_app)

    async def short_runner() -> tuple[int, float]:
        return await measure_request(args.url, short_payload, args.timeout, local_app=args.local_app)

    long_tasks = [asyncio.create_task(long_runner()) for _ in range(args.long_requests)]
    await asyncio.sleep(0.5)
    short_results = await asyncio.gather(*(short_runner() for _ in range(args.short_requests)))
    long_results = await asyncio.gather(*long_tasks)

    short_latencies = [latency for status, latency in short_results if status < 500]
    print(
        json.dumps(
            {
                "short_request_summary": summarize_latencies(short_latencies),
                "short_statuses": [status for status, _ in short_results],
                "long_statuses": [status for status, _ in long_results],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
