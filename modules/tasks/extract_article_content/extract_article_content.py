"""
Task: extract_article_content
Pool: cpu
Input:
    url           str  article URL
    html          str  raw HTML fetched by download_article
    note          str  optional user note
    url_slug      str  url slug (mandatory)
Output:
    text_len      int  character count of extracted text
    index_task_id str  ID of the created index_article task
    url_slug      str  url slug (mandatory)
Creates:
    index_article  — one; no dependencies (content is passed via input_data)
"""

import logging
import re
from typing import Dict, Any
from urllib.parse import urlparse

from modules.task_manager.task_manager import Task

log = logging.getLogger("task_extract_article_content")
POOL = "cpu"


async def run(task: Task, context: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    from modules.parser.parser import extract_content

    task_manager = context["task_manager"]
    url          = input_data["url"]
    html         = input_data["html"]
    note         = input_data.get("note", "")
    url_slug     = input_data["url_slug"]
    pool         = context["cpu_pool"]

    log.info(f"Starting extract_article_content for slug: {url_slug}")
    result = await pool.submit(lambda: extract_content(html), label="extract_article")
    text = result["markdown"]
    title = result["title"]

    domain   = urlparse(url).netloc
    
    # Since trafilatura with_metadata=True includes metadata in markdown, 
    # we use result["markdown"] as content.
    content = text

    # Instead of index_article, call chunk_article
    chunk_task = await task_manager.create_task(
        "chunk_article",
        {
            "url": url, 
            "content": text, 
            "url_slug": url_slug,
            "title": title
        },
    )

    return {
        "url_slug": url_slug
    }