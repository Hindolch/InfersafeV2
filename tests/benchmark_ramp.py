import argparse
import asyncio
import json
import statistics
import time

import httpx


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * p))
    return ordered[index]


async def one_request(client: httpx.AsyncClient, url: str, payload: dict) -> tuple[int, float]:
    start = time.perf_counter()
    response = await client.post(url, json=payload)
    return response.status_code, time.perf_counter() - start


async def run_level(url: str, model: str, concurrency: int, total_requests: int, max_tokens: int) -> dict:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Explain the relationship between TTFT and queue depth."}],
        "max_tokens": max_tokens,
        "stream": False,
    }
    latencies: list[float] = []
    statuses: list[int] = []
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(timeout=180.0) as client:
        async def worker() -> None:
            async with semaphore:
                status, latency = await one_request(client, url, payload)
                statuses.append(status)
                latencies.append(latency)

        started = time.perf_counter()
        await asyncio.gather(*(worker() for _ in range(total_requests)))
        duration = time.perf_counter() - started

    return {
        "concurrency": concurrency,
        "total_requests": total_requests,
        "duration_seconds": round(duration, 2),
        "throughput_rps": round(total_requests / duration, 2) if duration else 0.0,
        "p50_ms": round(statistics.median(latencies) * 1000, 2) if latencies else 0.0,
        "p95_ms": round(percentile(latencies, 0.95) * 1000, 2),
        "p99_ms": round(percentile(latencies, 0.99) * 1000, 2),
        "status_histogram": {str(code): statuses.count(code) for code in sorted(set(statuses))},
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Simple ramp benchmark for InferSafe.")
    parser.add_argument("--url", default="http://localhost:8000/v1/chat/completions")
    parser.add_argument("--model", default="local-vllm")
    parser.add_argument("--max-tokens", type=int, default=64)
    parser.add_argument("--requests", type=int, default=30)
    parser.add_argument("--levels", default="1,5,10")
    args = parser.parse_args()

    results = []
    for level in [int(item) for item in args.levels.split(",") if item.strip()]:
        results.append(await run_level(args.url, args.model, level, args.requests, args.max_tokens))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
