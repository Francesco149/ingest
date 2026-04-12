# fetcher_article

## Purpose
Fetches article HTML over HTTP using a browser User-Agent.

## Exports
```python
async def download_article(url: str, pool: WorkerPool) -> str
```

## Imports From
- `worker_pool`: `WorkerPool`
- `fetcher_url`: `slug` (for pool label only)

## Behavior Rules
- Uses `httpx.AsyncClient` with `follow_redirects=True`, timeout 30s
- Raises `httpx.HTTPStatusError` on non-2xx responses (via `resp.raise_for_status()`)
- Returns raw HTML string

## Must NOT
- Parse or process HTML — that is `parser.extract_content`'s responsibility
- Import from `engine`, `task_manager`, or any task module
