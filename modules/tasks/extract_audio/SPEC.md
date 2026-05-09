# tasks/extract_audio

## Purpose
Extracts 16kHz mono WAV audio from a video file using ffmpeg.

## Pool
cpu

## Input
```
video_path  str  path to the downloaded video
audio_path  str  destination path for the WAV file (set by download_subtitles)
url_slug str (mandatory)
```

## Output
```
audio_path  str  same as input — echoed so transcribe can read it via dep_ enrichment
url_slug str (mandatory)
```

## Creates
Nothing. (transcribe task is created upfront by download_subtitles.)

## Imports From
- `task_manager`: `Task`

## Behavior Rules
- ffmpeg command: `-ar 16000 -ac 1 -y {audio_path}`
- Runs ffmpeg directly inside the cpu worker assigned by `POOL = "cpu"`
- Raises `subprocess.CalledProcessError` if ffmpeg fails (task marked FAILED)

## Must NOT
- Import from any fetcher module
- Create the transcribe task — that is download_subtitles's responsibility
