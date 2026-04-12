"""
Task: index_video
Purpose: Assembles all chunk descriptions and the transcript into a Markdown document and indexes it into the RAG collection.
Pool: (none — pure I/O, runs in task_manager's asyncio loop)
Input (direct):
    url         str              original video URL
    url_slug    str              mandatory slug for the URL
    sub_result  tuple | None     (transcript_text, source) from download_subtitles, if subs found
    meta        dict             video metadata from yt-dlp
Input (via dep_ enrichment — all dependency outputs are injected as dep_{task_id}):
    From describe_single_chunk deps:  {"descriptions": str, "start_ts": int}
    From transcribe dep (if present): {"transcript": str}
    From summarize_video deps:       {"reasoning_text": str}
Output:
    filename  str  name of the written markdown file
    url_slug  str  mandatory slug for the URL
Creates: nothing
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from urllib.parse import urlparse

from modules.task_manager.task_manager import Task
from modules.indexer.indexer import save_and_upload

log = logging.getLogger("task_index_video")
POOL = "cpu"


async def run(task: Task, context: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    url_slug = input_data["url_slug"]
    url    = input_data.get("url")
    config = context["config"]
    KNOWLEDGE_DIR = Path(config["paths"]["knowledge_dir"])
    meta   = input_data.get("meta")

    # 1. Try to collect reasoned summaries first
    summaries = []
    for key, val in input_data.items():
        if key.startswith("dep_") and isinstance(val, dict) and "reasoning_text" in val:
            summaries.append(val["reasoning_text"])

    # 2. Fallback: Collect descriptions from chunk deps, sorted by start_ts for correct order.
    chunk_deps = [
        v for k, v in input_data.items()
        if k.startswith("dep_") and isinstance(v, dict) and "description" in v
    ]
    chunk_deps.sort(key=lambda v: v.get("start_ts", 0))
    all_descriptions = "\n\n".join(d["description"] for d in chunk_deps)

    # Transcript: from whisper dep or from subtitle result passed in input_data.
    transcript = next(
        (v["transcript"] for k, v in input_data.items()
         if k.startswith("dep_") and isinstance(v, dict) and "transcript" in v),
        None,
    )
    sub_result = input_data.get("sub_result")
    if transcript is None and sub_result:
        transcript = sub_result[0]

    date     = datetime.now().strftime("%Y-%m-%d")
    
    # Filename generation
    title = meta.get('title', 'Untitled') if meta else 'Untitled'
    title_part = title[:80]
    filename = f"{title_part}-{url_slug}.md"

    content = f"# {title}\n\n## Metadata\n- URL: {url}\n- Ingested: {date}\n"
    
    description_text = None
    if meta:
        content += "\n## Video Metadata\n"
        for key, value in meta.items():
            if key == 'description':
                description_text = value
                continue
            if key == 'duration_s' and value is None:
                continue
            if key == 'channel' and meta.get('uploader') == meta.get('channel'):
                continue
            
            display_val = value
            if isinstance(value, (int, float)):
                display_val = f"{value:,}"
            elif isinstance(value, list):
                display_val = ", ".join(map(str, value))
            elif key == 'upload_date' and isinstance(value, str) and len(value) == 8 and value.isdigit():
                display_val = f"{value[:4]}-{value[4:6]}-{value[6:8]}"
            
            content += f"- {key.replace('_', ' ').capitalize()}: {display_val}\n"

    if description_text:
        content += f"\n## Description\n{description_text}\n"

    # Content Assembly Logic: Prioritize summaries, fallback to raw descriptions
    if summaries:
        content += f"\n## Video Summary (Reasoned)\n\n" + "\n\n".join(summaries) + "\n"
    elif all_descriptions:
        content += f"\n## Visual Frame Descriptions\n\n{all_descriptions}\n"

    if transcript:
        if isinstance(transcript, list):
            # Handle structured list of dicts
            lines = []
            for entry in transcript:
                # Convert seconds to M:SS
                start_sec = entry.get('start', 0.0)
                minutes = int(start_sec // 60)
                seconds = int(start_sec % 60)
                time_str = f"[{minutes:02d}:{seconds:02d}]"
                text = entry.get('text', '').strip()
                if text:
                    lines.append(f"{time_str} {text}")
            transcript_text = "\n".join(f"- {l}" for l in lines if l.strip())
        else:
            # Handle raw string
            transcript_text = "\n".join(f"- {l}" for l in transcript.splitlines() if l.strip())
            
        content += f"\n## Transcript\n\n{transcript_text}\n"

    log.info(f"Indexing video: {filename} (summaries={'yes' if summaries else 'no'}, chunks={len(chunk_deps)}, transcript={'yes' if transcript else 'no'})")
    await save_and_upload(url, filename, content, config, KNOWLEDGE_DIR, replace_existing=True)

    return {"filename": filename, "url_slug": url_slug}