import asyncio
import json
import subprocess

import httpx

from tests.edge_cases.common import build_parser, completion_payload


async def stream_request(url: str, payload: dict, timeout: float) -> list[str]:
    chunks: list[str] = []
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", url, json=payload) as response:
            async for line in response.aiter_lines():
                if line:
                    chunks.append(line)
    return chunks


async def main() -> None:
    parser = build_parser("Edge Case 3: mid-stream replica failure")
    parser.add_argument("--kill-service", default="vllm-1")
    parser.add_argument("--compose-file", default="configs/docker-compose.yml")
    parser.add_argument("--kill-delay", type=float, default=2.0)
    args = parser.parse_args()

    payload = completion_payload(args.model, "Generate a very long numbered list.", max_tokens=1024, stream=True)
    task = asyncio.create_task(stream_request(args.url, payload, args.timeout))
    await asyncio.sleep(args.kill_delay)
    subprocess.run(["docker", "compose", "-f", args.compose_file, "kill", args.kill_service], check=False)
    chunks = await task
    print(json.dumps({"kill_service": args.kill_service, "received_chunks": len(chunks), "tail": chunks[-5:]}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
