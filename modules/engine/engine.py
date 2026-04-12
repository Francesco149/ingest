"""
Engine — pool lifecycle, config, ffprobe helper, and request entry points.
No processing logic lives here.
"""

import asyncio
import logging
import os
from pathlib import Path

from modules.config_loader import get_config

from modules.worker_pool.worker_pool import WorkerPool
from modules.fetcher_url.fetcher_url import normalize_url, is_video, slug, get_manga_id
from modules.fetcher_video.fetcher_video import get_video_metadata
from modules.fetcher_article.fetcher_article import download_article
from modules.task_manager.task_manager import TaskManager, TaskStatus

log = logging.getLogger("engine")

# ── config ────────────────────────────────────────────────────────────────────

config = get_config()

KNOWLEDGE_DIR  = Path(config["paths"]["knowledge_dir"])
DOWNLOADS_DIR  = Path(config["paths"]["downloads_dir"])

KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
(DOWNLOADS_DIR / "subtitles").mkdir(parents=True, exist_ok=True)

# ── worker pools ──────────────────────────────────────────────────────────────

download_pool = WorkerPool("download", config["workers"]["download"])
cpu_pool      = WorkerPool("cpu",      config["workers"]["cpu"])
cuda_pool     = WorkerPool("cuda",     config["workers"]["cuda"])
vision_pool   = WorkerPool("vision",   config["workers"]["vision"])

pools = {
    "download": download_pool,
    "cpu":      cpu_pool,
    "cuda":     cuda_pool,
    "vision":   vision_pool,
    "config":   config,
}

task_manager = TaskManager(DOWNLOADS_DIR.parent / "data" / "ingest.db"
                           if "db_path" not in config["paths"]
                           else Path(config["paths"]["db_path"]),
                           pools)

def start_pools():
    download_pool.start()
    cpu_pool.start()
    cuda_pool.start()
    vision_pool.start()
    asyncio.create_task(task_manager.start())
    log.info("all pools and task_manager started")

async def stop_pools():
    await task_manager.stop()
    log.info("stopping pools")

# ── helpers ───────────────────────────────────────────────────────────────────

async def get_video_duration(path: str) -> int:
    """Return video duration in seconds via ffprobe."""
    try:
        cmd = [
            config["paths"]["ffprobe_bin"], "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            return int(float(stdout.decode().strip()))
        log.error(f"ffprobe error: {stderr.decode()}")
        return 0
    except Exception as e:
        log.error(f"ffprobe failed: {e}")
        return 0

# ── request handlers ──────────────────────────────────────────────────────────

async def rerun_task(task_type: str, slug: str = None) -> int:
    """Resets all DONE tasks of a specific type back to PENDING."""
    log.info(f"rerunning tasks of type: {task_type} (slug: {slug})")
    if slug:
        task = await task_manager.db.find_task(task_type, "url_slug", slug)
        if task and task.status == TaskStatus.DONE:
            await task_manager.db.update_status(task.id, TaskStatus.PENDING)
            log.info(f"rerunning task {task.id} (slug: {slug})")
            return 1
        else:
            log.info(f"no DONE task found for {task_type} with slug: {slug}")
            return 0
    
    all_tasks = await task_manager.db.get_all_tasks()
    count = 0
    for task in all_tasks:
        if task.type == task_type and task.status == TaskStatus.DONE:
            task_slug = task.input_data.get('url_slug')
            log.debug(f"checking task {task.id} (type: {task.type}, slug: {task_slug})")
            await task_manager.db.update_status(task.id, TaskStatus.PENDING)
            count += 1
    return count

async def force_ingest(url: str, note: str = "force rerun") -> dict:
    """Cleans up existing data and re-triggers ingestion for a URL."""
    url = normalize_url(url)
    url_slug = slug(url)
    
    # 2. Clean up DB
    await task_manager.db.delete_tasks_by_identifiers(url=url, url_slug=url_slug)
    
    # 3. Clean up Knowledge Dir
    md_file = KNOWLEDGE_DIR / f"{url_slug}.md"
    if md_file.exists():
        md_file.unlink()
        log.info(f"Deleted existing knowledge file: {md_file}")

    # 4. Re-trigger
    if is_video(url):
        return await handle_video(url, note)
    elif get_manga_id(url, fingerprint=config['api']['manga_url_fingerprint']):
        return await handle_manga(url, note)
    else:
        # Fallback to article check or unknown
        return await handle_article(url, note)

async def handle_ingest(url: str, note: str) -> dict:
    """Main entry point for routing ingestion requests."""
    url = normalize_url(url)
    
    if is_video(url):
        result = await handle_video(url, note)
    elif get_manga_id(url, fingerprint=config['api']['manga_url_fingerprint']):
        result = await handle_manga(url, note)
    elif url.endswith(".pdf"):
        result = {"status": "todo", "message": "pdf support coming soon"}
    else:
        result = await handle_article(url, note)

    if result.get("status") not in ("ok", "todo", "pending"):
        result = await handle_unknown(url, note)
    
    return result

async def handle_video(url: str, note: str) -> dict:
    url      = normalize_url(url)
    meta     = get_video_metadata(url, config)
    video_slug = slug(url)

    existing = await task_manager.db.find_task("download_video", "url_slug", video_slug)
    if existing and existing.status != TaskStatus.FAILED:
        return {
            "status": existing.status.value,
            "task_id": existing.id,
            "title": existing.input_data.get("meta", {}).get("title", "Unknown")
        }

    task_id = await task_manager.create_task(
        "download_video",
        {
            "url":          url,
            "note":         note,
            "meta":         meta,
            "url_slug":     video_slug,
            "downloads_dir": str(DOWNLOADS_DIR),
            "sub_dir":      str(DOWNLOADS_DIR / "subtitles"),
        },
    )
    return {"status": "pending", "task_id": task_id, "title": meta.get("title", "Unknown")}


async def handle_article(url: str, note: str) -> dict:
    url = normalize_url(url)
    url_slug = slug(url)
    
    existing = await task_manager.db.find_task("download_article", "url", url)
    if existing and existing.status != TaskStatus.FAILED:
        return {"status": existing.status.value, "task_id": existing.id}

    task_id = await task_manager.create_task(
        "download_article",
        {"url": url, "url_slug": url_slug, "note": note},
    )
    return {"status": "pending", "task_id": task_id}


async def handle_manga(url: str, note: str) -> dict:
    url = normalize_url(url)
    gallery_id = get_manga_id(url, fingerprint=config['api']['manga_url_fingerprint'])
    url_slug = slug(url)

    existing = await task_manager.db.find_task("download_manga", "url_slug", url_slug)
    if existing and existing.status != TaskStatus.FAILED:
        return {"status": existing.status.value, "task_id": existing.id}

    task_id = await task_manager.create_task(
        "download_manga",
        {
            "url":           url,
            "gallery_id":   gallery_id,
            "download_dir": str(DOWNLOADS_DIR),
            "url_slug":     url_slug,
            "note":         note,
        },
    )
    return {"status": "pending", "task_id": task_id}


async def handle_unknown(url: str, note: str) -> dict:
    url = normalize_url(url)
    url_slug = slug(url)
    return {"status": "todo", "url_slug": url_slug, "message": f"No handler for {url}"}
