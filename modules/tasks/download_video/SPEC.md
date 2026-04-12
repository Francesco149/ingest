# tasks/download_video

## Purpose
Downloads the video file and fans out the chunk description + subtitle subtasks that form the rest of the DAG.

## Pool
download

## Input
```
url           str   normalized video URL
url_slug      str   8-char slug for stable file naming (mandatory)
downloads_dir str   directory to write the video file into
sub_dir       str   base dir for per-video subtitle subdirectories
note          str   optional user note
meta          dict  video metadata (title, uploader, etc.)
```

## Output
```
file_path      str        actual path of the downloaded video
duration       int        seconds, from ffprobe
desc_task_ids  list[str]  IDs of all created describe_single_chunk tasks
sub_task_id    str        ID of the created download_subtitles task
url_slug       str        primary identifier for tasks associated with the URL (mandatory)
```

## Creates
- `describe_single_chunk` × N — one per `chunk_duration` seconds; dep: this task
- `download_subtitles` — one; dep: this task; receives `url_slug` for subdir isolation

## Imports From
- `fetcher_video`: `download_video`
- `engine`: `get_video_duration`
- `task_manager`: `Task`

## Behavior Rules
- Idempotency: before creating a chunk task, checks `find_task("describe_single_chunk", "start_ts", start_ts)` AND verifies `existing.input_data["video_path"] == result_path` — must match both to reuse
- Always passes `url_slug` into `download_subtitles` input

## Must NOT
- Import from `fetcher_subtitles`, `parser`, or `indexer`
- Glob the downloads directory to find the result file — that is `fetcher_video`'s responsibility
