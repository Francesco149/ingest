# download_manga

## Purpose
Downloads an manga gallery, describes each image, summarizes, transcribes, and triggers indexing.

## Exports
```python
async def run(task: Task, context: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]
```

## Imports From
- `task_manager`: `Task`
- `modules.fetcher_manga.fetcher_manga`: `fetch_gallery`

## Input
gallery_id    str  manga gallery ID
download_dir  str  directory to save images
note          str  optional user note
url           str  url (for logging)
url_slug      str (mandatory)

## Output
gallery_id       str  echoed gallery ID
image_paths      list[str] paths to downloaded images
metadata         dict  gallery metadata
desc_task_ids    list[str] IDs of all created describe_manga_page tasks
transcribe_task_ids list[str] IDs of all created transcribe_manga tasks
url_slug          str (mandatory)
image_info        list[dict] list of image information (path, url, etc.)

## Behavior Rules
- Uses `fetch_gallery` to download images.
- Creates `describe_manga_page` tasks per chunk, then batches these into `summarize_manga` tasks, followed by `transcribe_manga` tasks.
- `summarize_manga` depends on a batch of `describe_manga_page` tasks; `transcribe_manga` depends on its `summarize_manga` task.
- `index_manga` task is created at the end, depending on all `transcribe_manga` tasks.
- Uses `download_pool` for the fetcher.

## Must NOT
- Import from `engine` directly (use `context`).
- Import from `task_manager` or any task module (except `Task` type).
