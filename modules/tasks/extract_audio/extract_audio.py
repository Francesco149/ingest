"""
Task: extract_audio
Pool: (none; submits ffmpeg to cpu_pool)
Purpose: Extracts 16kHz mono WAV audio from a video file using ffmpeg.
Input:
    video_path  str  path to the downloaded video file
    audio_path  str  destination path for the extracted WAV (set by download_subtitles)
    url_slug str (mandatory)
    desc_task_ids list[str] list of description task IDs
    metadata    dict  video metadata
Output:
    audio_path  str  same as input (echoed so transcribe can read it via dep_ enrichment)
    url_slug str (mandatory)
    desc_task_ids list[str]
    metadata    dict
Creates: nothing
"""

import logging
import subprocess
from typing import Dict, Any

from modules.task_manager.task_manager import Task

log = logging.getLogger("task_extract_audio")
POOL = None


async def run(task: Task, context: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    # 1. Extract mandatory identifier
    url_slug = input_data["url_slug"]
    url = input_data.get("url")
    config = context["config"]
    metadata = input_data.get("metadata", {})
    desc_task_ids = input_data.get("desc_task_ids", [])

    log.info(f"Starting extract_audio for slug: {url_slug}")

    try:
        video_path = input_data["video_path"]
        audio_path = input_data["audio_path"]
        pool       = context["cpu_pool"]

        log.info(f"Extracting audio: {video_path} → {audio_path}")

        def _run():
            subprocess.run([
                config["paths"]["ffmpeg_bin"], "-i", video_path,
                "-ar", "16000", "-ac", "1", "-y", audio_path,
            ], capture_output=True, check=True)

        await pool.submit(_run, label=f"extract_audio:{video_path}")

        return {"audio_path": audio_path, "url": url, "url_slug": url_slug, "desc_task_ids": desc_task_ids, "metadata": metadata}
    except Exception as e:
        log.error(f"Task extract_audio failed: {e}")
        raise
