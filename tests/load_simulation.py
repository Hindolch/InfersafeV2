import asyncio
import httpx
import pytest

@pytest.mark.asyncio
async def test_load_simulation():
    async def test_request(i):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(
                    "http://localhost:8000/v1/chat/completions",
                    json={
                        "model": "local-vllm",
                        "messages": [{"role": "user", "content": f"Load test {i}"}],
                        "max_tokens": 20,
                        "stream": False,
                    },
                )
                print(f"Request {i} - Status: {r.status_code}, Response: {r.text}")
                assert r.status_code == 200
        except Exception as e:
            pytest.fail(f"Request {i} failed: {e}")

    tasks = [test_request(i) for i in range(5)]
    await asyncio.gather(*tasks)
