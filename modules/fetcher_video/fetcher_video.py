"""
Video fetching — yt-dlp download and metadata extraction.
"""

import json
import logging
import os
import subprocess
from pathlib import Path

from modules.worker_pool.worker_pool import WorkerPool
from modules.fetcher_url.fetcher_url import slug as url_slug

log = logging.getLogger("fetcher-video")

_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".mov"}


def get_video_metadata(url: str, config: dict) -> dict:
    """Fetch video metadata via yt-dlp --dump-json. Returns empty dict on failure."""
    cookies = config["processing"]["cookies_from_browser"]
    cmd = [config["paths"]["yt_dlp_bin"], "--dump-json", "--no-playlist"]
    if cookies:
        cmd += ["--cookies-from-browser", cookies]
    cmd.append(url)

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        log.warning(f"metadata fetch failed for {url}: {r.stderr[:200]}")
        return {}

    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError as e:
        log.error(f"failed to parse metadata JSON for {url}: {e}")
        return {}

    return {
        "title":          data.get("title"),
        "uploader":       data.get("uploader"),
        "channel":        data.get("channel"),
        "upload_date":    data.get("upload_date"),
        "duration_s":     data.get("duration_s"),
        "view_count":     data.get("view_count"),
        "like_count":     data.get("like_count"),
        "description":    data.get("description", "")[:1000],
        "tags":           data.get("tags"),
        "categories":     data.get("categories"),
        "comment_count":  data.get("comment_count"),
    }


async def download_video(url: str, downloads_dir: str, video_slug: str, config: dict, pool: WorkerPool) -> str:
    """Download video to downloads_dir/video-{slug}.{ext}. Returns actual file path.

    Uses output template so yt-dlp handles multi-stream merges without a fixed
    extension. Finds the result by matching the slug prefix, so it never
    accidentally returns a file from a previous download.
    """
    formats: list[str] = config["processing"]["yt_formats"]
    cookies: str = config["processing"]["cookies_from_browser"]

    # %(ext)s lets yt-dlp choose the right extension after merging streams.
    out_template = os.path.join(downloads_dir, f"video-{video_slug}.%(ext)s")

    def _run() -> str:
        last_stderr = ""
        for fmt in formats:
            cmd = [
                config["paths"]["yt_dlp_bin"],
                "--format", fmt,
                "--output", out_template,
                "--no-playlist",
            ]
            if cookies:
                cmd += ["--cookies-from-browser", cookies]
            cmd.append(url)

            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode == 0:
                log.info(f"download succeeded with format {fmt!r}")
                break
            last_stderr = r.stderr
            log.info(f"format {fmt!r} failed, trying next. stderr: {r.stderr[:200]}")
        else:
            raise RuntimeError(f"all yt-dlp formats failed.\nLast error:\n{last_stderr}")

        # Find the specific file this download produced, by slug prefix.
        # This prevents returning a stale file from a previous video's download.
        dl_dir = Path(downloads_dir)
        files = [
            f for f in dl_dir.iterdir()
            if f.stem == f"video-{video_slug}" and f.suffix in _VIDEO_EXTENSIONS
        ]
        if not files:
            raise RuntimeError(f"no video file found after download (slug={video_slug})")
        return str(files[0])

    return await pool.submit(_run, label=f"dl_video:{video_slug}")
