# fetcher_manga

## Purpose
Fetches manga gallery metadata and downloads all images in the gallery.

## Exports
```python
async def fetch_gallery(gallery_id: str, download_dir: str, config: dict) -> dict
```

## Imports From
- `task_manager`: `RateLimitError`

## Behavior Rules
- Uses `httpx.AsyncClient` for API calls.
- Fetches metadata from `{manga_api_url}/galleries/{gallery_id}/`.
- Uses `manga_api_key` from `config['api']` for authentication via `Authorization: Key <api_key>` header.
- Builds image URLs from `metadata["image_servers"]` and each page `path`, then
  downloads images to `download_dir` as `image_{index:03d}.jpg`.
- Uses `config["manga"]["image_servers"]` when metadata does not include
  `image_servers`.
- Downloads page images directly with the local `httpx.AsyncClient` before the
  client context closes.
- Does not submit nested jobs to worker pools; `download_manga` is already
  scheduled on the download pool by the task manager.
- Returns a dictionary: `{metadata: ..., image_info: [...]}`.
- Raises errors if the gallery is not found or downloads fail.
- Raises `RateLimitError` if an image download returns a 429 status code.

## Must NOT
- Import from engine or any task module except task_manager.
