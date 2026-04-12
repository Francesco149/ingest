"""
Task: download_subtitles
Pool: download
Purpose: Downloads subtitles for a video and branches the DAG: with subs → summarize_video → index_video; without subs → extract_audio → transcribe → index_video.
Input:
    url         str   original video URL
    url_slug    str   (mandatory) 8-char slug matching the video download (for subdir isolation)
    target_path str   base directory for subtitle subdirectories (sub_dir)
    video_path  str   path to the downloaded video (for audio extraction fallback)
    desc_task_ids  list[str]  IDs of all describe_single_chunk tasks
    metadata    dict       video metadata from yt-dlp
Output:
    transcript      str                     the transcript text (from subs or transcription)
    summarize_task_id str                       ID of the created summarize_video task (subs path only)
    index_task_id   str                       ID of the created index_video task
    audio_task_id   str                       ID of the created extract_audio task (no-subs path only)
    url_slug        str                       (mandatory) primary identifier for tasks associated with the URL
Creates:
    summarize_video  — if subs found; dep: this task
    index_video      — always; deps vary by path
    extract_audio    — no-subs path only; dep: this task
    transcribe       — no-subs path only; dep: extract_audio
"""

import logging
import re
from pathlib import Path
from typing import Dict, Any

from modules.task_manager.task_manager import Task


log = logging.getLogger("task_download_subtitles")
POOL = "download"


async def run(task: Task, context: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    from modules.fetcher_subtitles.fetcher_subtitles import download_subtitles

    task_manager = context["task_manager"]
    config       = context["config"]
    url          = input_data["url"]
    url_slug     = input_data["url_slug"]
    target_dir   = input_data["target_path"]
    video_path   = input_data["video_path"]
    pool         = context["download_pool"]

    # Inputs passed directly from download_video
    desc_task_ids = input_data.get("desc_task_ids", [])
    metadata      = input_data.get("metadata", {})

    log.info(f"Starting download_subtitles for slug: {url_slug}")

    try:
        log.info(f"downloading subtitles: {url} (slug={url_slug})")
        result = await download_subtitles(url, target_dir, url_slug, config, pool=pool)

        if result:
            transcript_segments = result[0]
            log.info(f"Subtitles found! {len(transcript_segments)} segments found.")
            
            # Path A: Subtitles found -> summarize -> index
            sum_task = await task_manager.create_task(
                "summarize_video",
                {
                    "url": url,
                    "transcript": transcript_segments,
                    "meta": metadata,
                    "url_slug": url_slug,
                    "desc_task_ids": desc_task_ids,
                },
                dependencies=[task.id] + desc_task_ids,
            )

            # Create idx_task once with the full transcript
            idx_task = await task_manager.create_task(
                "index_video",
                {"url": url, "transcript": transcript_segments, "meta": metadata, "url_slug": url_slug},
                dependencies=[task.id, sum_task] + desc_task_ids,
            )
            
            log.info(f"subtitles found — queued summarize_video ({sum_task}) and index_video ({idx_task})")
            return {
                "transcript": transcript_segments, 
                "summarize_task_ids": [sum_task], 
                "index_task_id": idx_task, 
                "url_slug": url_slug
            }
        
        else:
            log.info("No subtitles found in download_subtitles.")
            # Path B: No subtitles -> extract audio -> transcribe -> summarize -> index
            audio_path = str(Path(video_path).with_suffix(".wav"))

            audio_task = await task_manager.create_task(
                "extract_audio",
                {
                    "video_path": video_path, 
                    "audio_path": audio_path, 
                    "url": url, 
                    "url_slug": url_slug,
                    "desc_task_ids": desc_task_ids,
                    "metadata": metadata,
                },
                dependencies=[task.id],
            )
            transcribe_task = await task_manager.create_task(
                "transcribe",
                {"url_slug": url_slug},  # audio_path injected via dep_ enrichment from extract_audio
                dependencies=[audio_task],
            )
            sum_task = await task_manager.create_task(
                "summarize_video",
                {
                    "url": url,
                    "url_slug": url_slug,
                    "meta": metadata,
                    "desc_task_ids": desc_task_ids,
                },
                dependencies=[transcribe_task] + desc_task_ids,
            )
            idx_task = await task_manager.create_task(
                "index_video",
                {"url": url, "meta": metadata, "url_slug": url_slug},
                dependencies=[transcribe_task, sum_task] + desc_task_ids,
            )
            log.info(
                f"no subtitles — queued extract_audio ({audio_task}) "
                f"→ transcribe ({transcribe_task}) → summarize_video ({sum_task}) "
                f"→ index_video ({idx_task})"
            )
            return {"transcript": None, "audio_task_id": audio_task, "index_task_id": idx_task, "url_slug": url_slug}
            
    except Exception as e:
        log.error(f"Task download_subtitles failed: {e}")
        raise