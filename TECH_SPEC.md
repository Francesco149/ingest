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
- `200 {"status": "pending", "task_id": "..."}` — manga queued
- `200 {"status": "todo", "message": "..."}` — unsupported type
- `400 {"error": "no url provided"}`

### `GET|POST /rerun/{task_type}`
Resets existing `DONE` tasks of the given type back to `PENDING`.

**Query parameters:**
- `slug` optional URL slug. When present, only a matching `DONE` task with that
  `input_data.url_slug` is reset.

**Response:**
```json
{ "rerun_count": 1 }
```

### `POST /force`
Deletes existing task rows and local Markdown output for a URL, then starts a
fresh ingest for that URL. This is destructive for that URL's current local task
state.

**Request body:**
```json
{ "url": "https://..." }
```

**Responses:**
- Same success payloads as `POST /ingest`
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
Returns all task rows:

```json
{
  "tasks": [
    {
      "id": "...",
      "type": "download_video",
      "status": "PENDING",
      "created_at": "2026-05-09T12:00:00",
      "error": null
    }
  ]
}
```

### `GET /knowledge`
Lists Markdown files in `knowledge_dir`, newest first:

```json
{ "files": ["example.md"] }
```

---

## 2. Task types

Each task is a file in `tasks/{task_type}.py` that exports `async def run(task, context, input_data)`.

The `context` dict contains: `download_pool`, `cpu_pool`, `cuda_pool`, `vision_pool`, `task_manager`, `config`.

Dependencies' `output_data` are injected into `input_data` as `dep_{task_id}` keys before `run()` is called.

| Task type                | Pool     | Creates children                         |
|--------------------------|----------|------------------------------------------|
| `download_video`         | download | `describe_single_chunk` × N, `download_subtitles` |
| `describe_single_chunk`  | cuda     | nothing                                  |
| `download_subtitles`     | download | `index_video` + optionally `extract_audio`, `transcribe` |
| `extract_audio`          | —        | nothing; submits ffmpeg work to `cpu_pool` |
| `transcribe`             | —        | nothing; submits whisper work to `cuda_pool` |
| `index_video`            | —        | nothing                                  |
| `download_article`       | download | `extract_article_content`                |
| `extract_article_content`| cpu      | `chunk_article`                          |
| `chunk_article`          | —        | `summarize_text_chunk` × N, `summarize_article` |
| `summarize_text_chunk`   | —        | nothing                                  |
| `summarize_article`      | —        | `index_article`                          |
| `index_article`          | —        | nothing                                  |
| `download_manga`         | download | `describe_manga_page` × N, `summarize_manga` × N, `transcribe_manga` × N, `index_manga` |
| `describe_manga_page`    | vision   | nothing                                  |
| `summarize_manga`        | vision   | nothing                                  |
| `transcribe_manga`       | vision   | nothing                                  |
| `index_manga`            | cpu      | nothing                                  |

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

**Captioning prompt:** `config.toml` / `config.example.toml`
`[prompts.video_describe].user`. All durable LLM prompt text belongs under
`[prompts.*]` config sections.

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
whisper_model   = "/opt/ai-lab/models/whisper/ggml-medium.bin"
db_path         = "/opt/ai-lab/data/ingest.db"
downloads_dir   = "/opt/ai-lab/downloads"        # optional, defaults to knowledge_dir/downloads
yt_dlp_bin      = "yt-dlp"
ffmpeg_bin      = "ffmpeg"
ffprobe_bin     = "ffprobe"

[api]
llama_base             = "http://localhost:8080"
reasoning_llama_base   = "http://localhost:8080"
openwebui_base         = "http://localhost:3000"
openwebui_key          = "..."
openwebui_collection   = "..."
manga_api_key          = ""
manga_api_url          = "https://example.com/manga/api/v1/"
manga_url_fingerprint  = "example.com/g/"
reasoning_max_tokens   = 3000
llama_timeout          = 1200
llama_temperature      = 0.7

[workers]
download = 2
cpu      = 4
cuda     = 1
vision   = 2

[processing]
chunk_duration = 30    # seconds per describe_single_chunk task
fps            = 2.0   # frames per second for llama-video extraction
cookies_from_browser = "chromium"
yt_formats = [
  "bestvideo[height<=1080]+bestaudio/best",
  "bestvideo+bestaudio/best",
]

[manga]
vision_uses_metadata = false
description_batch_size = 3
description_overlap = 1
vision_max_tokens = 1024
vision_temperature = 0.2
summary_max_batch_size = 16

[prompts.video_describe]
user = "..."

[prompts.manga_describe]
system = "..."
user_template = "..."

[prompts.manga_summarize]
system = "..."
instructions = "..."

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
