"""
Task: download_article
Pool: download
Purpose: Fetches article HTML and fans out to extract_article_content.
Input:
    url   str  normalized article URL
    note  str  optional user note
    url_slug str (mandatory)
Output:
    url   str  echoed (for dep_ enrichment consumers)
    html  str  raw HTML of the article page
    url_slug str (mandatory)
Creates:
    extract_article_content  — one; dep: this task
"""

import logging
from typing import Dict, Any

from modules.task_manager.task_manager import Task

log = logging.getLogger("task_download_article")
POOL = "download"


async def run(task: Task, context: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    from modules.fetcher_article.fetcher_article import download_article

    task_manager = context["task_manager"]
    url          = input_data["url"]
    note         = input_data.get("note", "")
    url_slug     = input_data["url_slug"]
    pool         = context["download_pool"]

    try:
        log.info(f"Starting download_article for slug: {url_slug}")
        html = await download_article(url, pool)

        child = await task_manager.create_task(
            "extract_article_content",
            {"url": url, "html": html, "note": note, "url_slug": url_slug},
            dependencies=[task.id],
        )
        log.info(f"queued extract_article_content ({child})")

        return {"url_slug": url_slug, "url": url, "html": html}
    except Exception as e:
        log.error(f"Task download_article failed: {e}")
        raise
