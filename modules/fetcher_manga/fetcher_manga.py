import logging
import httpx
import asyncio
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from modules.task_manager.task_manager import RateLimitError

log = logging.getLogger('modules.fetcher_manga.fetcher_manga')


def _api_cache_key(url: str, request_body: str) -> str:
    payload = json.dumps(
        {"url": url, "request_body": request_body},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_db_path(config: dict) -> Path | None:
    db_path = config.get("paths", {}).get("db_path")
    return Path(db_path) if db_path else None


def _ensure_cache_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS manga_api_cache (
            cache_key TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            request_body TEXT NOT NULL,
            response_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )


def _get_cached_api_response(config: dict, url: str, request_body: str) -> dict[str, Any] | None:
    db_path = _cache_db_path(config)
    if db_path is None:
        return None

    db_path.parent.mkdir(parents=True, exist_ok=True)
    cache_key = _api_cache_key(url, request_body)
    with sqlite3.connect(db_path) as conn:
        _ensure_cache_table(conn)
        row = conn.execute(
            "SELECT response_json FROM manga_api_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()
    if row is None:
        return None

    log.info(f'Using cached manga API response for {url}')
    return json.loads(row[0])


def _store_cached_api_response(
    config: dict,
    url: str,
    request_body: str,
    response_json: dict[str, Any],
) -> None:
    db_path = _cache_db_path(config)
    if db_path is None:
        return

    db_path.parent.mkdir(parents=True, exist_ok=True)
    cache_key = _api_cache_key(url, request_body)
    now = datetime.now().isoformat()
    with sqlite3.connect(db_path) as conn:
        _ensure_cache_table(conn)
        conn.execute(
            """
            INSERT INTO manga_api_cache (
                cache_key,
                url,
                request_body,
                response_json,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                response_json = excluded.response_json,
                updated_at = excluded.updated_at
            """,
            (
                cache_key,
                url,
                request_body,
                json.dumps(response_json),
                now,
                now,
            ),
        )
        conn.commit()


async def _gather_fail_fast(tasks: list[asyncio.Task]) -> list[str]:
    pending = set(tasks)
    results: dict[asyncio.Task, str] = {}

    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_EXCEPTION)
        for task in done:
            exc = task.exception()
            if exc is not None:
                for pending_task in pending:
                    pending_task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                raise exc
            results[task] = task.result()

    return [results[task] for task in tasks]


async def fetch_gallery(gallery_id: str, download_dir: str, config: dict) -> dict:
    """
    Fetches gallery metadata and downloads all images.
    """
    api_url = f"{config['api']['manga_api_url'].rstrip('/')}/galleries/{gallery_id}/"
    download_path = Path(download_dir)
    download_path.mkdir(parents=True, exist_ok=True)

    api_key = config['api']['manga_api_key']

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        log.info(f'Fetching metadata for gallery {gallery_id}')
        headers = {'Authorization': f'Key {api_key}'} if api_key else {}
        request_body = ""
        metadata = _get_cached_api_response(config, api_url, request_body)
        if metadata is None:
            try:
                resp = await client.get(api_url, headers=headers)
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    raise RateLimitError()
                raise
            metadata = resp.json()
            _store_cached_api_response(config, api_url, request_body, metadata)
        log.debug(f'Metadata keys: {list(metadata.keys())}')

        # In a real manga API scenario, the image URLs would be in the metadata
        # For this implementation, we assume the API provides a 'pages' list of objects
        pages = metadata.get('pages', [])
        
        if not pages:
            log.warning(f'No pages found for gallery {gallery_id}')
            return {'metadata': metadata, 'image_info': []}

        image_info = []
        batch_tasks = []
        batch_info_map = []
        servers = metadata.get('image_servers') or config['manga']['image_servers']
        batch_size = max(1, int(config['manga']['image_download_batch_size']))
        concurrency = max(1, int(config['manga']['image_download_concurrency']))
        semaphore = asyncio.Semaphore(concurrency)
        
        async def _download_task(u, p):
            async with semaphore:
                log.info(f'Downloading {u}')
                try:
                    img_resp = await client.get(u, headers=headers)
                    img_resp.raise_for_status()
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        raise RateLimitError()
                    raise
            
            p.write_bytes(img_resp.content)
            return str(p)

        async def _flush_batch() -> None:
            nonlocal batch_tasks, batch_info_map
            if not batch_tasks:
                return

            downloaded_paths = await _gather_fail_fast(batch_tasks)
            for idx, path in enumerate(downloaded_paths):
                info_idx = batch_info_map[idx]
                image_info[info_idx]['path'] = path
            batch_tasks = []
            batch_info_map = []

        for i, page in enumerate(pages):
            url_path = page.get('path')
            if not url_path:
                log.warning(f"Page {i} missing 'path' key. Page content: {page}")
                continue
            
            server = servers[i % len(servers)]
            url = f"https://{server}/{url_path}"
            file_path = download_path / f'image_{i:03d}.jpg'

            image_info.append({'path': str(file_path), 'url': url})

            if file_path.exists():
                log.info(f"File already exists: {file_path}, skipping download.")
                continue

            task = asyncio.create_task(_download_task(url, file_path))
            task.set_name(f"dl_img:{i:03d}")
            batch_tasks.append(task)
            batch_info_map.append(len(image_info) - 1)
            if len(batch_tasks) >= batch_size:
                await _flush_batch()

        # Keep page downloads inside this task's download worker. Do not submit
        # nested jobs to worker pools; the task manager owns pool scheduling.
        await _flush_batch()

        return {
            'metadata': metadata,
            'image_info': image_info
        }
