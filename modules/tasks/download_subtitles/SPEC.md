# Task: download_subtitles
Pool: download
Purpose: Downloads subtitles for a video and branches the DAG: with subs → index_video; without subs → extract_audio → transcribe → index_video.

Input:
    url         str   original video URL
    url_slug    str   (mandatory) 8-char slug matching the video download (for subdir isolation)
    target_path str   base directory for subtitle subdirectories (sub_dir)
    video_path  str   path to the downloaded video (for audio extraction fallback)
    desc_task_ids  list[str]  IDs of all describe_single_chunk tasks (via dep_ enrichment)
    meta           dict       video metadata from yt-dlp (via dep_ enrichment)

Output:
    sub_result      tuple[str, str] | None   (transcript_text, source) or None
    index_task_id   str   ID of the created index_video task
    audio_task_id   str   ID of the created extract_audio task (no-subs path only)
    url_slug        str   (mandatory) primary identifier for tasks associated with the URL

Creates:
    index_video     — always; deps vary by path
    extract_audio   — no-subs path only; dep: this task
    transcribe      — no-subs path only; dep: extract_audio

## Imports From
- `fetcher_subtitles`: `download_subtitles`
- `task_manager`: `Task`

## Behavior Rules
- `url_slug` is passed through to `fetcher_subtitles` so it can write to a per-video subdir
- `desc_task_ids` are extracted from the single `dep_*` dict in `input_data`
- The full no-subs DAG (audio + transcribe + index) is created upfront so the graph is visible immediately

## Must NOT
- Import from `fetcher_video`, `parser`, or `indexer`
- Attempt to parse or read subtitle files — that is `fetcher_subtitles`'s responsibility
