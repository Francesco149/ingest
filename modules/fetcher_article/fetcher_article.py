"""
Article fetching — plain HTTP with browser User-Agent.
"""

import logging

import httpx

from modules.worker_pool.worker_pool import WorkerPool
from modules.fetcher_url.fetcher_url import slug as url_slug

log = logging.getLogger("fetcher-article")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


async def download_article(url: str, pool: WorkerPool) -> str:
    """Fetch article HTML. Returns raw HTML string."""
    async def _run():
        async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=_HEADERS) as c:
            resp = await c.get(url)
        resp.raise_for_status()
        return resp.text

    return await pool.submit(_run, label=f"dl_article:{url_slug(url)}")
