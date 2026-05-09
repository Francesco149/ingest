# tasks/download_subtitles

## Purpose
Downloads subtitles for a video and branches the DAG: with subtitles,
`summarize_video -> index_video`; without subtitles,
`extract_audio -> transcribe -> summarize_video -> index_video`.

## Pool
download

## Input
```
url            str        original video URL
url_slug       str        mandatory URL slug
target_path    str        base directory for subtitle subdirectories
video_path     str        path to downloaded video for audio fallback
desc_task_ids  list[str]  IDs of all describe_single_chunk tasks
metadata       dict       video metadata from yt-dlp
```

## Output
```
transcript           list[dict] | None  subtitle segments if found
summarize_task_ids   list[str]          created summarize_video task IDs, subs path only
index_task_id        str                created index_video task ID
audio_task_id        str                created extract_audio task ID, no-subs path only
url_slug             str                mandatory URL slug
```

## Creates
- `summarize_video` — always; deps vary by path
- `index_video` — always; deps vary by path
- `extract_audio` — no-subs path only; dep: this task
- `transcribe` — no-subs path only; dep: extract_audio

## Imports From
- `fetcher_subtitles`: `download_subtitles`
- `task_manager`: `Task`

## Behavior Rules
- `url_slug` is passed through to `fetcher_subtitles` so it can write to a per-video subdir
- Caption path: `summarize_video` depends on this task and all description tasks;
  `index_video` depends on this task, the summary task, and all description tasks.
- No-caption path: full fallback DAG is created upfront so the graph is visible
  immediately.

## Must NOT
- Import from `fetcher_video`, `parser`, or `indexer`
- Attempt to parse or read subtitle files — that is `fetcher_subtitles`'s responsibility
