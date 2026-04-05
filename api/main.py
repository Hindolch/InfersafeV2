from api.gateway_impl import app, build_async_client, configure_runtime_state
"""
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from models.inference_engine import TinyLLamaModel
from pydantic import BaseModel
from utils.batching import RequestQueueManager, BatchedRequest
from fastapi.responses import PlainTextResponse
from utils.logger import logger
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST, Summary
from fastapi.responses import Response
import time
from utils.model_manager import ModelManager
from utils.multi_model_manager import MultiModelManager
from utils.autoscaler import Autoscaler
import traceback
from typing import List
from prometheus_client import make_asgi_app
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.inference_engine import load_model

if os.getenv("TESTING") == "1":
    from unittest.mock import AsyncMock
    model_worker = AsyncMock()
else:
    model_worker = load_model()


NUM_MODEL_WORKERS = 3
BATCH_SIZE_LIMIT = 32  # Maximum number of requests in a batch
REQUEST_COUNT = Counter("inference_requests_total", "Total number of inference requests")
RETRY_COUNT = Counter("inference_retries_total", "Total number of retries")
INFERENCE_LATENCY = Histogram("inference_request_duration_seconds", "Duration of inference requests")

MAX_RETRIES = 5
INFERENCE_TIMEOUT = 10  # seconds

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf")
MODEL_PATH = os.path.abspath(MODEL_PATH)

if os.getenv("TESTING") != "1":
    model = TinyLLamaModel(model_path=MODEL_PATH)

model_manager = MultiModelManager(
    num_workers=NUM_MODEL_WORKERS,
    model_path=MODEL_PATH
)

# model_worker = model_manager.get_least_busy_model()  # ❌ Replaced by get_model_worker for better testability

# ✅ New: Use this getter so we can easily mock it in tests
def get_model_worker():
    return model_manager.get_least_busy_model()

autoscaler = Autoscaler(model_manager, scale_interval=5)  # Autoscaler instance

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "InfersafeV2 is up!"}

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
request_manager = RequestQueueManager()

class GenerateRequest(BaseModel):
    prompt: str
    max_tokens: int = 128

@app.on_event("startup")
async def on_startup():
    asyncio.create_task(autoscaler.start_scaling())
    asyncio.create_task(request_manager.start_loop(process_batch))

@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

async def process_batch(batch: list[BatchedRequest]):
    print(f"[BATCH] Processing {len(batch)} requests")
    REQUEST_COUNT.inc(len(batch))
    
    failed_requests = []

    for i, req in enumerate(batch):
        success = False
        for attempt in range(MAX_RETRIES + 1):
            start = time.time()
            try:
                worker = get_model_worker()  # ✅ Use the getter here
                token_stream = await asyncio.wait_for(
                    worker.generate(req.prompt, req.max_tokens),
                    timeout=INFERENCE_TIMEOUT
                )
                duration = time.time() - start
                INFERENCE_LATENCY.observe(duration)
                if not req.future.done():
                    req.future.set_result(token_stream)
                logger.info(f"[BATCH] Request {i} processed by {worker.name} in {duration:.2f} seconds")
                success = True
                break
            except asyncio.TimeoutError:
                RETRY_COUNT.inc()
                logger.error(f"[TIMEOUT] Request #{i+1} attempt {attempt+1} timed out after {INFERENCE_TIMEOUT}s")
                if attempt == MAX_RETRIES:
                    failed_requests.append(req)
            except Exception as e:
                RETRY_COUNT.inc()
                duration = time.time() - start
                INFERENCE_LATENCY.observe(duration)
                logger.error(f"[ERROR] Failed request #{i+1} on attempt {attempt+1} with {worker.name}: {e}")
                if attempt == MAX_RETRIES:
                    failed_requests.append(req)
        
        if not success and not req.future.done():
            req.future.set_exception(Exception("Inference failed after all retries"))
    
    logger.info(f"[BATCH] Completed batch of {len(batch)} requests. Failed: {len(failed_requests)}")

@app.post("/generate-batch")
async def generate_via_batch(request: GenerateRequest):
    if os.getenv("TESTING") == "1":
        future = asyncio.Future()
        req = BatchedRequest(prompt=request.prompt, max_tokens=request.max_tokens, future=future)
        await process_batch([req])
        result = await future
        return PlainTextResponse(result)

    future = request_manager.enqueue(request.prompt, request.max_tokens)

    async def stream():
        try:
            queue_size = len(request_manager.queue)
            dynamic_timeout = min(30.0, 10.0 + (queue_size / BATCH_SIZE_LIMIT) * 5.0)
            
            result = await asyncio.wait_for(future, timeout=dynamic_timeout)
            for token in result.split():
                yield f"{token} ".encode()
        except asyncio.TimeoutError:
            logger.error(f"Request timed out after {dynamic_timeout}s")
            yield b"Error: Request timed out, please try again"
        except Exception as e:
            logger.error(f"Exception during streaming: {e}")
            traceback.print_exc()
            yield f"Error: {type(e).__name__}: {str(e)}".encode()

    return StreamingResponse(stream(), media_type="text/plain")

@app.post("/reload-model")
def reload_model():
    try:
        model_manager.reload_model()
        return "Model reloaded successfully"
    except Exception as e:
        return Response(f"Failed to reload model: {str(e)}", status_code=500)
"""
