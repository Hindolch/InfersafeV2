import argparse
import asyncio
import json
import time

import httpx


async def run(url: str, model: str, stream: bool) -> None:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Give me a one sentence summary of continuous batching."}],
        "max_tokens": 64,
        "stream": stream,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        if stream:
            start = time.perf_counter()
            first_chunk_at = None
            chunks: list[str] = []
            async with client.stream("POST", url, json=payload) as response:
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if first_chunk_at is None:
                        first_chunk_at = time.perf_counter()
                    chunks.append(line)
            print(
                json.dumps(
                    {
                        "mode": "stream",
                        "status": response.status_code,
                        "ttft_ms": round(((first_chunk_at or time.perf_counter()) - start) * 1000, 2),
                        "chunks_seen": len(chunks),
                        "tail": chunks[-5:],
                    },
                    indent=2,
                )
            )
            return

        response = await client.post(url, json=payload)
        print(json.dumps({"mode": "sync", "status": response.status_code, "body": response.json()}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="InferSafe smoke test for OpenAI-compatible chat completions.")
    parser.add_argument("--url", default="http://localhost:8000/v1/chat/completions")
    parser.add_argument("--model", default="local-vllm")
    parser.add_argument("--stream", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.url, args.model, args.stream))
