"""
Subtitle fetching — yt-dlp VTT download with per-video isolation.
"""

import logging
import os
import subprocess
from pathlib import Path

from modules.worker_pool.worker_pool import WorkerPool

log = logging.getLogger("fetcher-subtitles")


from typing import Any

async def download_subtitles(
    url: str,
    subs_base_dir: str,
    video_slug: str,
    config: dict,
    pool: WorkerPool,
) -> tuple[list[dict[str, Any]], str] | None:
    """Try manual then auto-generated subtitles for url.

    Writes to subs_base_dir/{video_slug}/ — a unique subdirectory per video
    so concurrent downloads and successive ingest runs never pick up each
    other's .vtt files.

    Returns (transcript_segments, source) or None if no subtitles found.
    """
    cookies: str = config["processing"]["cookies_from_browser"]

    # Unique dir per video: prevents glob from picking up another video's subs.
    sub_dir = os.path.join(subs_base_dir, video_slug)
    os.makedirs(sub_dir, exist_ok=True)

    def _run():
        from modules.parser.parser import _parse_vtt
        from youtube_transcript_api import YouTubeTranscriptApi
        import re

        # 1. Try YouTubeTranscriptApi first if it's a YouTube URL
        if "youtube.com" in url or "youtu.be" in url:
            try:
                # Simple extraction of video ID from common URL patterns
                video_id_match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
                if video_id_match:
                    video_id = video_id_match.group(1)
                    transcript = YouTubeTranscriptApi().fetch(video_id)
                    formatted = [
                        {
                            "start": entry.start,
                            "end": entry.start + entry.duration,
                            "text": entry.text.replace("\n", " "),
                        }
                        for entry in transcript.snippets
                    ]
                    if formatted:
                        log.info(f"YouTubeTranscriptApi found subs for slug={video_slug}")
                        return formatted, "auto-generated"
            except Exception as e:
                log.debug(f"YouTubeTranscriptApi failed: {e}")

        # 2. Fallback to yt-dlp
        for auto in (False, True):
            sub_base = os.path.join(sub_dir, "subs")
            flag = "--write-auto-subs" if auto else "--write-subs"
            cmd = [
                config["paths"]["yt_dlp_bin"], "--skip-download", flag,
                "--sub-lang", "en", "--sub-format", "vtt",
                "--output", sub_base, "--no-playlist",
            ]
            if cookies:
                cmd += ["--cookies-from-browser", cookies]
            cmd.append(url)

            subprocess.run(cmd, capture_output=True)

            # Only glob within this video's isolated subdir.
            vtt_files = list(Path(sub_dir).glob("*.vtt"))
            if vtt_files:
                raw = vtt_files[0].read_text(encoding="utf-8")
                segments = _parse_vtt(raw)
                if segments:
                    source = "auto-generated" if auto else "manual"
                    log.info(f"subs found ({source}) for slug={video_slug}")
                    return segments, source

        log.info(f"no subtitles found for slug={video_slug}")
        return None

    return await pool.submit(_run, label=f"dl_subs:{video_slug}")
