"""
Task: index_manga
Pool: cpu
Purpose: Indexes manga gallery content into the RAG knowledge base.
Input:
    gallery_id    str  manga gallery ID
    metadata      dict  gallery metadata (title, tags)
    url           str  original source URL
    url_slug      str  (mandatory)
    dep_*         dict  task outputs containing reasoning_text and transcript_text
Output:
    url_slug  str  (mandatory)
    filename  str (optional)
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from modules.task_manager.task_manager import Task
from modules.indexer.indexer import save_and_upload

log = logging.getLogger('task_index_manga')
POOL = "cpu"

async def run(task: Task, context: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    gallery_id = input_data['gallery_id']
    metadata = input_data['metadata']
    url_slug = input_data['url_slug']
    url = input_data['url']
    
    # Get text from dependencies
    reasoning_parts = []
    transcript_parts = []
    for k, v in input_data.items():
        if k.startswith("dep_") and isinstance(v, dict):
            if "reasoning_text" in v:
                reasoning_parts.append((v.get("start_page", 0), v["reasoning_text"]))
            if "transcript_text" in v:
                transcript_parts.append((v.get("start_page", 0), v["transcript_text"]))

    reasoning_text = "\n\n---\n\n".join([p[1] for p in sorted(reasoning_parts, key=lambda x: x[0])])
    transcript_text = "\n\n---\n\n".join([p[1] for p in sorted(transcript_parts, key=lambda x: x[0])])

    log.info(f"Starting index_manga for slug: {url_slug}")

    if not reasoning_text or not transcript_text:
        log.error(f"Task index_manga failed: No reasoning_text or transcript_text found in input_data for slug: {url_slug}")
        raise ValueError(f"No reasoning_text or transcript_text found in input_data for slug: {url_slug}")

    # Construct Filename
    title_obj = metadata.get('title', {})
    best_title = title_obj.get('japanese') or title_obj.get('pretty') or title_obj.get('english')
    if best_title:
        filename = f"{best_title[:90]}-{url_slug}.md"
    else:
        filename = f"{datetime.now().strftime('%Y-%m-%d')}-{url_slug}.md"
    
    try:
        config = context["config"]
        KNOWLEDGE_DIR = Path(config["paths"]["knowledge_dir"])
        
        await save_and_upload(
            url=url,
            filename=filename,
            content=reasoning_text + "\n\n" + transcript_text,
            config=config,
            knowledge_dir=KNOWLEDGE_DIR,
            replace_existing=True
        )
        
        log.info(f'Successfully indexed gallery {gallery_id} with filename {filename}')
        return {'filename': filename, 'url_slug': url_slug}
            
    except Exception as e:
        log.error(f"Task index_manga failed: {e}")
        raise
