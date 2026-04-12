# fetcher_manga

## Purpose
Fetches manga gallery metadata and downloads all images in the gallery.

## Exports
```python
async def fetch_gallery(gallery_id: str, download_dir: str, pool: WorkerPool, config: dict) -> dict
```

## Imports From
- `worker_pool`: `WorkerPool`
- `task_manager`: `RateLimitError`

## Behavior Rules
- Uses `httpx.AsyncClient` for API calls.
- Fetches metadata from manga API (e.g., `/api/v2/galleries/{gallery_id}`).
- Uses `manga_api_key` from `config['api']` for authentication via `Authorization: Key <api_key>` header.
- Downloads all images in the gallery to `download_dir`.
- Uses `pool` to manage concurrent image downloads.
- Returns a dictionary: `{metadata: ..., image_info: [...]}`.
- Raises errors if the gallery is not found or downloads fail.
- Raises RateLimitError if the API returns a 429 status code.

## Must NOT
- Import from engine or any task module except task_manager.
