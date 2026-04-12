# fetcher_subtitles

## Purpose
yt-dlp subtitle download with per-video directory isolation to prevent cross-video VTT file collisions.

## Exports
```python
async def download_subtitles(
    url: str,
    subs_base_dir: str,
    video_slug: str,
    config: dict,
    pool: WorkerPool,
) -> tuple[list[dict[str, Any]], str] | None
```

## Imports From
- `worker_pool`: `WorkerPool`
- `parser`: `_parse_vtt` (imported inside the sync closure to avoid event-loop issues)

## Behavior Rules
- Writes to `subs_base_dir/{video_slug}/` — a unique subdirectory per video slug
- Creates the subdirectory with `os.makedirs(..., exist_ok=True)` before any yt-dlp call
- Tries manual subs first (`--write-subs`), then auto-generated (`--write-auto-subs`)
- Globs only within `{subs_base_dir}/{video_slug}/` — never the base dir
- Cookies: passes `--cookies-from-browser` if `config["processing"]["cookies_from_browser"]` is non-empty
- Returns `(text, "manual")` or `(text, "auto-generated")` or `None` if no subs found
- Does not raise on yt-dlp failure — absence of .vtt files means no subs

## Must NOT
- Write subtitle files to a shared/flat directory
- Glob outside its own per-video subdir
- Import from `engine`, `task_manager`, or any task module
