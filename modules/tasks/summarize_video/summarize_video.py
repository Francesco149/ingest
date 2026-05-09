import logging
from typing import Any, Dict
import json
import re
from modules.task_manager.task_manager import Task
from modules.llm_openai import chat

log = logging.getLogger("tasks.summarize_video")
POOL = "vision"

def extract_segment(transcript_list: list[dict[str, Any]], start_ts: float, end_ts: float) -> str:
    """
    Extracts text from a list of transcript dictionaries between start_ts and end_ts.
    """
    extracted_text = []
    for entry in transcript_list:
        s = entry.get('start', 0.0)
        e = entry.get('end', 0.0)
        if s < end_ts and e > start_ts:
            text = entry.get('text', '')
            if text:
                extracted_text.append(str(text).strip())
    return " ".join(extracted_text)

async def run(task: Task, context: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    task_manager = context['task_manager']
    log.info(f"Starting summarize_video task: {task.id}")
    
    log.info(f"summarize_video input_data keys: {list(input_data.keys())}")
    for k, v in input_data.items():
        if k.startswith("dep_"):
            if isinstance(v, dict):
                # Log the keys available in the dependency and a snippet of the transcript if it exists
                transcript_snippet = v.get('transcript', '')[:50] if v.get('transcript') else "N/A"
                log.info(f"Dependency {k} has keys {list(v.keys())} | transcript snippet: '{transcript_snippet}...'")
            else:
                log.info(f"Dependency {k} is not a dictionary: {type(v)}")

    url_slug = input_data.get("url_slug")
    if not url_slug:
        raise ValueError("url_slug missing")

    transcript_segments = input_data.get("transcript")
    metadata = input_data.get("metadata") or input_data.get("meta") or {}
    desc_task_ids = input_data.get("desc_task_ids", [])

    dep_outputs = [
        v for k, v in input_data.items()
        if k.startswith("dep_") and isinstance(v, dict)
    ]
    if transcript_segments is None:
        transcript_segments = next(
            (v.get("transcript") for v in dep_outputs if v.get("transcript") is not None),
            [],
        )
    if not metadata:
        metadata = next((v.get("metadata") for v in dep_outputs if v.get("metadata")), {})
    if not desc_task_ids:
        desc_task_ids = next((v.get("desc_task_ids") for v in dep_outputs if v.get("desc_task_ids")), [])

    # Convert segments to a human-readable string for LLM context
    if isinstance(transcript_segments, list):
        transcript_text_for_llm = "\n".join(
            [f"[{int(e['start']//60):02d}:{int(e['start']%60):02d}] {e['text']}" 
             for e in transcript_segments if isinstance(e, dict)]
        )
    else:
        transcript_text_for_llm = str(transcript_segments)

    # Extract transcript and build content body from segments
    # transcript_segments is resolved from dep_ enrichment or input_data
    segment_lines = []
    for tid in desc_task_ids:
        dt = await task_manager.db.get_task(tid)
        if dt and dt.output_data:
            start = dt.output_data.get("start_ts", 0.0)
            end = dt.output_data.get("end_ts", 0.0)
            text = (
                extract_segment(transcript_segments, start, end)
                if isinstance(transcript_segments, list)
                else ""
            )
            if text:
                segment_lines.append(f"[{start:.2f}-{end:.2f}] {text}")
            
            # Include visual description if available
            desc_text = dt.output_data.get("description")
            if desc_text:
                segment_lines.append(f"[Visual] {desc_text}")

    content_body = "\n\n".join(segment_lines)

    prompt_cfg = context['config']['prompts']['video_summarize']
    user_msg = prompt_cfg['user_template'].format(
        title=metadata.get('title', 'Unknown Title'),
        tags=metadata.get('tags', ''),
        transcript=transcript_text_for_llm,
        visual_descriptions=content_body,
    )

    reasoning_text = await chat(
        prompt=user_msg,
        system_prompt=prompt_cfg['system'],
        temperature=1.0,
        config=context['config']
    )
    
    if not reasoning_text:
        log.error('No response text generated from LLM.')
        raise RuntimeError('No response text generated from LLM.')

    return {"reasoning_text": reasoning_text, "url_slug": url_slug, "metadata": metadata}
