# fetcher_video

## Purpose
yt-dlp video download and metadata extraction. All calls are subprocess-based and run inside a WorkerPool.

## Exports
```python
def get_video_metadata(url: str, config: dict) -> dict
async def download_video(url: str, downloads_dir: str, video_slug: str, config: dict, pool: WorkerPool) -> str
```

## Imports From
- `worker_pool`: `WorkerPool`
- `fetcher_url`: `slug` (for pool labels only)

## Behavior Rules
- `get_video_metadata`: runs `yt-dlp --dump-json` synchronously (called before any pool task); returns `{}` on failure rather than raising
- `download_video`:
  - Output template: `downloads_dir/video-{video_slug}.%(ext)s` — lets yt-dlp choose extension after stream merge
  - Iterates `config["processing"]["yt_formats"]` in order; first success wins
  - Cookies: passes `--cookies-from-browser {cookies_from_browser}` if `config["processing"]["cookies_from_browser"]` is non-empty
  - Finds result by matching `stem == "video-{video_slug}"` in downloads_dir — never globs the whole directory
  - Raises `RuntimeError` if no matching file found after all formats exhausted

## Must NOT
- Import from `engine`, `task_manager`, or any task module
- Use a fixed output path (no `--output path/file.mp4`) — always use `%(ext)s` template
- Pass `--dump-json` to download commands (metadata-only flag)
- Return the first file found in the directory — must match by slug prefix
