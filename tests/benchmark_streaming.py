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


async def one_stream_request(client: httpx.AsyncClient, url: str, payload: dict) -> dict:
    started = time.perf_counter()
    first_chunk_at: float | None = None
    previous_chunk_at: float | None = None
    chunk_gaps: list[float] = []
    status_code = 0
    chunk_count = 0

    async with client.stream("POST", url, json=payload) as response:
        status_code = response.status_code
        async for chunk in response.aiter_text():
            if not chunk.strip():
                continue
            now = time.perf_counter()
            chunk_count += 1
            if first_chunk_at is None:
                first_chunk_at = now
            elif previous_chunk_at is not None:
                chunk_gaps.append(now - previous_chunk_at)
            previous_chunk_at = now

    completed = time.perf_counter()
    ttft = (first_chunk_at - started) if first_chunk_at is not None else 0.0
    return {
        "status_code": status_code,
        "duration_seconds": completed - started,
        "ttft_seconds": ttft,
        "chunk_count": chunk_count,
        "tbt_samples": chunk_gaps,
    }


async def run_level(url: str, model: str, concurrency: int, total_requests: int, max_tokens: int) -> dict:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Explain KV cache and queue depth in two short points."}],
        "max_tokens": max_tokens,
        "stream": True,
    }
    semaphore = asyncio.Semaphore(concurrency)
    results: list[dict] = []

    async with httpx.AsyncClient(timeout=180.0) as client:
        async def worker() -> None:
            async with semaphore:
                results.append(await one_stream_request(client, url, payload))

        started = time.perf_counter()
        await asyncio.gather(*(worker() for _ in range(total_requests)))
        duration = time.perf_counter() - started

    statuses = [result["status_code"] for result in results]
    ttfts = [result["ttft_seconds"] for result in results if result["ttft_seconds"] > 0]
    tbts = [sample for result in results for sample in result["tbt_samples"]]

    return {
        "concurrency": concurrency,
        "total_requests": total_requests,
        "duration_seconds": round(duration, 2),
        "throughput_rps": round(total_requests / duration, 2) if duration else 0.0,
        "status_histogram": {str(code): statuses.count(code) for code in sorted(set(statuses))},
        "ttft_p50_ms": round(statistics.median(ttfts) * 1000, 2) if ttfts else 0.0,
        "ttft_p95_ms": round(percentile(ttfts, 0.95) * 1000, 2),
        "ttft_p99_ms": round(percentile(ttfts, 0.99) * 1000, 2),
        "tbt_p50_ms": round(statistics.median(tbts) * 1000, 2) if tbts else 0.0,
        "tbt_p95_ms": round(percentile(tbts, 0.95) * 1000, 2),
        "tbt_p99_ms": round(percentile(tbts, 0.99) * 1000, 2),
        "tbt_sample_count": len(tbts),
        "avg_chunks_per_request": round(
            sum(result["chunk_count"] for result in results) / len(results), 2
        ) if results else 0.0,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Streaming benchmark for InfersafeV2.")
    parser.add_argument("--url", default="http://localhost:8000/v1/chat/completions")
    parser.add_argument("--model", default="local-vllm")
    parser.add_argument("--max-tokens", type=int, default=64)
    parser.add_argument("--requests", type=int, default=12)
    parser.add_argument("--levels", default="1,2,4")
    args = parser.parse_args()

    results = []
    for level in [int(item) for item in args.levels.split(",") if item.strip()]:
        results.append(await run_level(args.url, args.model, level, args.requests, args.max_tokens))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
