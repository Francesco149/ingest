# tasks/transcribe

## Purpose
Runs whisper.cpp on an audio file to produce a full transcript.

## Pool
none; submits whisper work to `cuda_pool`

## Input (direct)
```
url_slug      str        url slug
audio_path    str        optional fallback for manual task creation
desc_task_ids list[str]  optional fallback for manual task creation
metadata      dict       optional fallback for manual task creation
```

## Input (via dep_ enrichment from extract_audio)
```
audio_path     str        path to the 16kHz mono WAV
desc_task_ids  list[str]  description task IDs
metadata       dict       video metadata
```

## Output
```
transcript     str        full transcript text
url_slug       str        url slug
desc_task_ids  list[str]  description task IDs
metadata       dict       video metadata
```

## Creates
Nothing. (index_video task is created upfront by download_subtitles.)

## Imports From
- `task_manager`: `Task`

## Behavior Rules
- `audio_path` is resolved: first from `dep_*` enrichment, fallback to `input_data.get("audio_path")` for manual task creation
- Raises `ValueError` if no `audio_path` is found
- whisper output written to a `tempfile.TemporaryDirectory` as `out.srt`
- Raises `RuntimeError` if whisper returns non-zero or output file missing
- Whisper flags: `-osrt -of {out_base} --language auto -ng`

## Must NOT
- Import from any fetcher module
- Create the index_video task — that is download_subtitles's responsibility
