# TECH_SPEC.md

## 1. API

### `POST /ingest`
Routes by content type and returns immediately. All processing is async.

**Request body:**
```json
{ "url": "https://...", "note": "optional context" }
```

**Responses:**
- `200 {"status": "pending", "task_id": "...", "title": "..."}` — video queued
- `200 {"status": "pending", "task_id": "..."}` — article queued  
- `200 {"status": "todo", "message": "..."}` — unsupported type
- `400 {"error": "no url provided"}`

### `GET /status`
```json
{
  "pools": {
    "download": {"workers": 2, "queued": 0},
    "cpu":      {"workers": 4, "queued": 0},
    "cuda":     {"workers": 1, "queued": 0},
    "vision":   {"workers": 2, "queued": 0}
  },
  "tasks": {"total": 42}
}
```

### `GET /tasks`
Returns all task rows: `id`, `type`, `status`, `created_at`, `error`.

### `GET /knowledge`
Lists markdown files in `knowledge_dir`, newest first.

---

## 2. Task types

Each task is a file in `tasks/{task_type}.py` that exports `async def run(task, context, input_data)`.

The `context` dict contains: `download_pool`, `cpu_pool`, `cuda_pool`, `vision_pool`, `task_manager`, `config`.

Dependencies' `output_data` are injected into `input_data` as `dep_{task_id}` keys before `run()` is called.

| Task type                | Pool     | Creates children                         |
|--------------------------|----------|------------------------------------------|
| `download_video`         | download | `describe_single_chunk` × N, `download_subtitles` |
| `describe_single_chunk`  | vision   | nothing                                  |
| `download_subtitles`     | download | `index_video` + optionally `extract_audio`, `transcribe` |
| `extract_audio`          | cpu      | nothing                                  |
| `transcribe`             | cuda     | nothing                                  |
| `index_video`            | —        | nothing                                  |
| `download_article`       | download | *(not yet implemented in engine)*        |
| `extract_article_content`| cpu      | `index_article`                          |
| `index_article`          | —        | nothing                                  |

---

## 3. TaskDB schema

SQLite table `tasks`:

| Column        | Type | Notes                                    |
|---------------|------|------------------------------------------|
| `id`          | TEXT | UUID primary key                         |
| `type`        | TEXT | maps to `tasks/{type}.py`                |
| `status`      | TEXT | PENDING / RUNNING / DONE / FAILED / CANCELLED |
| `dependencies`| TEXT | JSON array of task IDs                   |
| `input_data`  | TEXT | JSON; `retriable: true` opts into restart reset |
| `output_data` | TEXT | JSON; written on DONE                    |
| `created_at`  | TEXT | ISO timestamp                            |
| `updated_at`  | TEXT | ISO timestamp                            |
| `error_msg`   | TEXT | set on FAILED                            |

**Restart behaviour:** On startup, `RUNNING` → `PENDING` (interrupted). `FAILED` with `input_data.retriable == true` → `PENDING` (transient error).

**Dispatch locking:** `_try_lock_task` does a single `UPDATE … WHERE status = 'PENDING'` and checks `rowcount` to prevent double-dispatch.

---

## 4. Fetcher

- **URL normalization:** strips `utm_*`, `si`, `pp`, `feature`, `ref`, `igshid`; YouTube short/share URLs → `watch?v=`
- **Video download:** `yt-dlp -S res:720 --format bestvideo[height<=1080]+bestaudio/best`, falls back to `best`
- **Subtitles:** manual subs first, then auto-generated; `--sub-lang en --sub-format vtt`
- **Article fetch:** `httpx` with a browser User-Agent, `follow_redirects=True`

---

## 5. Video processing

**Clip extraction (per chunk):**
```
ffmpeg -i {video} -ss {start} -t {duration} -vf scale=-1:540
       -c:v libx264 -preset veryfast -crf 23 -c:a aac -y {clip}
```

**Frame extraction:** `llama_video.Extractor` at `config.processing.fps` (default 2.0), max 64 frames, collapsed into super-frames by `Preprocessor`.

**Captioning prompt** (in `tasks/describe_single_chunk.py`):
```
Explain what happens in this video, no preamble, no outro.
This is part of a longer video, so don't say "at the end of the video" or
"the last scene", just explain what happens. No "the video shows/contains" either.
Don't overthink it, just loosely describe the action.
```

**Audio extraction:**
```
ffmpeg -i {video} -ar 16000 -ac 1 -y {audio.wav}
```

**Transcription:** `whisper-cli -m {model} -f {audio} -otxt -of {out} --language auto -ng`

---

## 6. Configuration (`config.toml`)

```toml
[paths]
knowledge_dir   = "/opt/ai-lab/knowledge"
knowledge_index = "/opt/ai-lab/knowledge/.index.json"
whisper_bin     = "/opt/ai-lab/whisper.cpp/build/bin/whisper-cli"
whisper_model   = "/opt/ai-lab/whisper.cpp/models/ggml-medium.bin"
db_path         = "/opt/ai-lab/data/ingest.db"
downloads_dir   = "/opt/ai-lab/downloads"        # optional, defaults to knowledge_dir/downloads

[api]
llama_base            = "http://localhost:8080"
openwebui_base        = "http://localhost:3000"
openwebui_key         = "..."
openwebui_collection  = "..."

[workers]
download = 2
cpu      = 4
cuda     = 1
vision   = 2

[processing]
chunk_duration = 30    # seconds per describe_single_chunk task
fps            = 2.0   # frames per second for llama-video extraction

[server]
port = 8083
```

---

## 7. Indexer

- Writes Markdown to `knowledge_dir/{filename}`
- Uploads to OpenWebUI RAG via `/api/v1/files/` (multipart) then adds to collection
- Tracks `{url_slug: [{file, owui_file_id, filename}]}` in `.index.json`
- `replace_existing=True` deletes previous local file and RAG entry for the same URL before writing

---

## 8. Known issues

See `DESIGN.md § Known issues` for the full list. Summary:

- `retriable` tasks have no max retry count
- `on_event` deprecation warning from FastAPI
- Duplicate `download_subtitles` possible if `download_video` re-executes
