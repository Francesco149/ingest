"""
Task: index_article
Pool: (none — pure I/O)
Purpose: Writes the assembled article Markdown to disk and uploads it to the RAG collection.
Input:
    url_slug  str  (mandatory)
    url       str  original article URL
    filename  str  target markdown filename
    content   str  full markdown content to write
Output:
    url_slug  str  (mandatory)
    status    str  "indexed"
    filename  str  echoed filename
Creates: nothing
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from modules.task_manager.task_manager import Task
from modules.indexer.indexer import save_and_upload

log = logging.getLogger("task_index_article")
POOL = "cpu"


async def run(task: Task, context: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    url_slug = input_data["url_slug"]
    url      = input_data["url"]
    content  = input_data["content"]
    title    = input_data["title"]
    summary  = input_data.get("summary", "")
    ingest_date = datetime.now().strftime("%Y-%m-%d")
    config   = context["config"]
    KNOWLEDGE_DIR = Path(config["paths"]["knowledge_dir"])

    log.info(f"Starting index_article for slug: {url_slug}")

    try:
        title_slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:50]
        new_filename = f"{title_slug}-{url_slug}.md"
        
        summary_block = f"\n\n{summary}\n\n" if summary else "\n\n"
        date_block = f"Ingest date: {ingest_date}\n\n"
        content_with_date = f"# {title}{summary_block}{date_block}{content}"
        
        log.info(f"Indexing article: {new_filename}")
        await save_and_upload(url, new_filename, content_with_date, config, KNOWLEDGE_DIR, replace_existing=True)

        return {
            "url_slug": url_slug,
            "status": "indexed", 
            "filename": new_filename
        }
    except Exception as e:
        log.error(f"Task index_article failed: {e}")
        raise