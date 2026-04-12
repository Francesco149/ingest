# engine

## Purpose
Wires config, worker pools, and task_manager together. Provides ffprobe helper and the two HTTP handler entry points. Contains no processing logic.

## Exports
```python
config: dict
KNOWLEDGE_DIR: Path
DOWNLOADS_DIR: Path
download_pool: WorkerPool
cpu_pool: WorkerPool
cuda_pool: WorkerPool
vision_pool: WorkerPool
task_manager: TaskManager

def start_pools() -> None
async def stop_pools() -> None
async def get_video_duration(path: str) -> int
async def handle_ingest(url: str, note: str) -> dict
async def handle_video(url: str, note: str) -> dict
async def handle_article(url: str, note: str) -> dict
async def handle_manga(url: str, note: str) -> dict
async def handle_unknown(url: str, note: str) -> dict
async def rerun_task(task_type: str, slug: str = None) -> int
async def force_ingest(url: str, note: str = "force rerun") -> dict
```

## Imports From
- `worker_pool`: `WorkerPool`
- `fetcher_url`: `normalize_url`, `is_video`, `slug`
- `fetcher_video`: `get_video_metadata`
- `fetcher_article`: `download_article`
- `task_manager`: `TaskManager`, `TaskStatus`

## Behavior Rules
- Config is loaded at module level from `INGEST_CONFIG` env var or `/opt/ai-lab/ingest/config.toml`
- `handle_video` passes `url_slug`, `downloads_dir`, and `sub_dir` in task input so tasks never need to re-derive paths
- `sub_dir` is always `DOWNLOADS_DIR / "subtitles"` — `fetcher_subtitles` creates per-video subdirs within it
- `get_video_duration` uses `ffprobe` via `asyncio.create_subprocess_exec`; returns 0 on failure rather than raising
- `start_pools` calls `.start()` on all four pools then schedules `task_manager.start()` as an asyncio task
- `handle_video`, `handle_article`, and `handle_manga` implement request-level idempotency by checking for existing non-failed/cancelled tasks before creating new ones

## Must NOT
- Contain any video processing, subtitle parsing, or indexing logic
- Import from `fetcher_subtitles` — subtitle fetching belongs to the task layer
- Hardcode paths — all paths come from config
