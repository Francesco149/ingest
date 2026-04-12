"""
API — FastAPI routes for the ingestion service.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from modules.engine import engine

logging.basicConfig(
    level=getattr(logging, os.environ.get("INGEST_LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine.start_pools()
    yield
    await engine.stop_pools()

app = FastAPI(lifespan=lifespan)

# ── routes ────────────────────────────────────────────────────────────────────

@app.post("/ingest")
async def ingest(request: Request):
    body = await request.json()
    url  = body.get("url", "").strip()
    note = body.get("note", "")
    if not url:
        return JSONResponse({"error": "no url provided"}, status_code=400)

    log.info(f"ingest request: {url}")
    result = await engine.handle_ingest(url, note)

    return JSONResponse(result)


@app.api_route("/rerun/{task_type}", methods=["GET", "POST"])
async def rerun_task(task_type: str, slug: str = None):
    count = await engine.rerun_task(task_type, slug=slug)
    return {"rerun_count": count}


@app.post("/force")
async def force_ingest(request: Request):
    body = await request.json()
    url = body.get("url", "").strip()
    if not url:
        return JSONResponse({"error": "no url provided"}, status_code=400)
    
    log.info(f"force ingest request: {url}")
    result = await engine.force_ingest(url)
    return JSONResponse(result)


@app.get("/knowledge")
async def list_knowledge():
    files = sorted(
        engine.KNOWLEDGE_DIR.glob("*.md"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    return {"files": [f.name for f in files]}


@app.get("/status")
async def status():
    return {
        "pools": {
            "download": {"workers": engine.download_pool.n_workers, "queued": engine.download_pool.depth},
            "cpu":      {"workers": engine.cpu_pool.n_workers,      "queued": engine.cpu_pool.depth},
            "cuda":     {"workers": engine.cuda_pool.n_workers,     "queued": engine.cuda_pool.depth},
            "vision":   {"workers": engine.vision_pool.n_workers,   "queued": engine.vision_pool.depth},
        },
        "tasks": {"total": len(await engine.task_manager.db.get_all_tasks())},
    }


@app.get("/tasks")
async def list_tasks():
    tasks = await engine.task_manager.db.get_all_tasks()
    return {"tasks": [
        {
            "id":         t.id,
            "type":       t.type,
            "status":     t.status.value,
            "created_at": t.created_at,
            "error":      t.error_msg,
        }
        for t in tasks
    ]}