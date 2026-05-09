"""
Task: extract_article_content
Pool: cpu
Input:
    url           str  article URL
    html          str  raw HTML fetched by download_article
    note          str  optional user note
    url_slug      str  url slug (mandatory)
Output:
    url_slug      str  url slug (mandatory)
Creates:
    chunk_article  — one; content and metadata are passed directly in input_data
"""

import logging
from typing import Dict, Any

from modules.task_manager.task_manager import Task

log = logging.getLogger("task_extract_article_content")
POOL = "cpu"


async def run(task: Task, context: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    from modules.parser.parser import extract_content

    task_manager = context["task_manager"]
    url          = input_data["url"]
    html         = input_data["html"]
    url_slug     = input_data["url_slug"]

    log.info(f"Starting extract_article_content for slug: {url_slug}")
    result = extract_content(html)
    text = result["markdown"]
    title = result["title"]

    log.info(
        f"Parsed article content for slug={url_slug}: "
        f"title={title!r}, chars={len(text)}"
    )
    chunk_task = await task_manager.create_task(
        "chunk_article",
        {
            "url": url,
            "content": text,
            "url_slug": url_slug,
            "title": title,
        },
    )
    log.info(f"Queued chunk_article ({chunk_task}) for slug={url_slug}")

    return {
        "url_slug": url_slug
    }
