# tasks/transcribe

## Purpose
Runs whisper.cpp on an audio file to produce a full transcript.

## Pool
cpu

## Input (direct)
```
(none required — audio_path is injected via dep_ enrichment)
```

## Input (via dep_ enrichment from extract_audio)
```
audio_path  str  path to the 16kHz mono WAV
```

## Output
```
transcript  str  full transcript text
url_slug    str  url slug
```

## Creates
Nothing. (index_video task is created upfront by download_subtitles.)

## Imports From
- `task_manager`: `Task`

## Behavior Rules
- `audio_path` is resolved: first from `dep_*` enrichment, fallback to `input_data.get("audio_path")` for manual task creation
- Raises `ValueError` if no `audio_path` is found
- whisper output written to a `tempfile.TemporaryDirectory` as `out.txt`
- Raises `RuntimeError` if whisper returns non-zero or output file missing
- Whisper flags: `-otxt -of {out_base} --language auto -ng`

## Must NOT
- Import from any fetcher module
- Create the index_video task — that is download_subtitles's responsibility
