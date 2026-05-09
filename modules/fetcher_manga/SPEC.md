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
- Fetches metadata from `{manga_api_url}/galleries/{gallery_id}/`.
- Uses `manga_api_key` from `config['api']` for authentication via `Authorization: Key <api_key>` header.
- Builds image URLs from `metadata["image_servers"]` and each page `path`, then
  downloads images to `download_dir` as `image_{index:03d}.jpg`.
- Uses `pool` to manage concurrent image downloads.
- Returns a dictionary: `{metadata: ..., image_info: [...]}`.
- Raises errors if the gallery is not found or downloads fail.
- Raises `RateLimitError` if an image download returns a 429 status code.

## Must NOT
- Import from engine or any task module except task_manager.
