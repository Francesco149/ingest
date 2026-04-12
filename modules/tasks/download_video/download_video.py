"""
Task: download_video
Purpose: Downloads the video file and fans out the chunk description + subtitle subtasks.
Pool: download
Input:
    url           str   normalized video URL
    url_slug      str   8-char slug for stable file naming (mandatory)
    downloads_dir str   directory to write the video file into
    sub_dir       str   base directory for per-video subtitle subdirectories
    note          str   optional user note (passed through to metadata)
    meta          dict  video metadata from yt-dlp (title, uploader, etc.)
Output:
    file_path      str        actual path of the downloaded file
    duration       int        video duration in seconds (from ffprobe)
    desc_task_ids  list[str]  IDs of all created describe_single_chunk tasks
    sub_task_id    str        ID of the created download_subtitles task
    url_slug       str        primary identifier for tasks associated with the URL (mandatory)
Creates:
    describe_single_chunk  — one per chunk_duration-second segment; dep: this task
    download_subtitles     — one; dep: this task
    (download_subtitles then creates the rest of the DAG)
"""

import logging
from typing import Dict, Any

from modules.task_manager.task_manager import Task
from modules.tasks.utils import get_batches

log = logging.getLogger("task_download_video")
POOL = "download"


async def run(task: Task, context: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    from modules.fetcher_video.fetcher_video import download_video
    from modules.engine.engine import get_video_duration

    task_manager  = context["task_manager"]
    config        = context["config"]
    url           = input_data["url"]
    url_slug      = input_data["url_slug"]
    downloads_dir = input_data["downloads_dir"]
    sub_dir       = input_data["sub_dir"]
    pool          = context["download_pool"]
    meta          = input_data.get("meta")

    log.info(f"Starting download_video for slug: {url_slug}")
    result_path = await download_video(url, downloads_dir, url_slug, config, pool=pool)
    log.info(f"Getting video duration for slug: {url_slug}")
    duration = await get_video_duration(result_path)
    log.info(f"Obtained video duration for slug: {url_slug}")

    chunk_duration = config["processing"]["chunk_duration"]
    n_chunks       = len(range(0, duration, chunk_duration))
    log.info(f"duration: {duration}s → {n_chunks} chunk(s), file: {result_path}")

    # Idempotent chunk creation: reuse an existing non-cancelled chunk task for
    # the same (video_path, start_ts) pair if the server crashed between run()
    # returning and update_status(DONE) being written.
    desc_task_ids = []
    for start_ts in range(0, duration, chunk_duration):
        end_ts   = min(start_ts + chunk_duration, duration)
        existing = await task_manager.db.find_task("describe_single_chunk", "start_ts", start_ts)
        # Only reuse if it belongs to the same video file — different videos may
        # share the same start_ts values.
        if existing and existing.input_data.get("video_path") == result_path:
            log.info(f"reusing chunk task {existing.id} for {start_ts}-{end_ts}")
            desc_task_ids.append(existing.id)
        else:
            dt = await task_manager.create_task(
                "describe_single_chunk",
                {
                    "video_path": result_path,
                    "url":        url,
                    "url_slug":   url_slug,
                    "start_ts":   start_ts,
                    "end_ts":     end_ts,
                    "retriable":  True,
                },
                dependencies=[task.id],
            )
            desc_task_ids.append(dt)

    sub_task = await task_manager.create_task(
        "download_subtitles",
        {
            "url":           url,
            "url_slug":      url_slug,
            "target_path":   sub_dir,
            "video_path":    result_path,
            "desc_task_ids": desc_task_ids,
            "metadata":      meta,
        },
        dependencies=[task.id],
    )

    return {
        "file_path":     result_path,
        "duration":      duration,
        "desc_task_ids": desc_task_ids,
        "sub_task_id":   sub_task,
        "url_slug":      url_slug,
        "url":           url,
        "meta":          meta,
    }
