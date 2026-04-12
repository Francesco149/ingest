# ingest-v2

Downloads videos and articles, processes them with local AI (llama-video for frame captioning, whisper.cpp for transcription), and indexes results into an OpenWebUI RAG collection as Markdown files.

---

## Data Flow

```
POST /ingest
    │
    ▼
api.py ──► engine.py ──► task_manager.create_task("download_video" | "download_article")
                │
                └── task_manager (SQLite DAG scheduler, 1s poll loop)
                        │
                        ├── tasks/download_video.py        (download pool)
                        │       ├── tasks/describe_single_chunk.py × N  (vision pool)
                        │       └── tasks/download_subtitles.py          (download pool)
                        │               ├── [subs found] → tasks/index_video.py
                        │               └── [no subs]   → tasks/extract_audio.py
                        │                                       └── tasks/transcribe.py
                        │                                               └── tasks/index_video.py
                        │
                        └── tasks/download_article.py      (download pool)
                                └── tasks/extract_article_content.py   (cpu pool)
                                        └── tasks/index_article.py
```

### Key principles

**DAG task scheduler.** Each unit of work is a `Task` row in SQLite with an explicit `dependencies` list. The scheduler dispatches any task whose dependencies are all `DONE`. Tasks are resumable across restarts and the graph is inspectable via `GET /tasks`.

**Tasks are isolated modules.** Each file in `tasks/` declares its input schema, output schema, and what child tasks it creates at the top of the file.

**No processing logic in `engine.py`.** Engine owns: pool lifecycle, config loading, `ffprobe` helper, and the two HTTP handler entry points.

**Fetcher is split by concern.** Each fetcher file handles exactly one transport (URL utils, video download, subtitle download, article HTTP). Tasks import only the fetcher they need.

---

## Module Index

| Module | Role |
| --- | --- |
| `api.py` | FastAPI routes, lifespan management |
| `engine.py` | Config, pool wiring, ffprobe, request entry points |
| `task_manager.py` | SQLite DAG scheduler, dispatch loop, dep_ enrichment |
| `worker_pool.py` | Async worker pool with thread-executor fallback |
| `fetcher_url.py` | URL normalization, slug, is_video — no I/O |
| `fetcher_video.py` | yt-dlp video download and metadata |
| `fetcher_subtitles.py` | yt-dlp subtitle download, per-video isolated subdir |
| `fetcher_article.py` | httpx article HTML fetch |
| `parser.py` | VTT text extraction, HTML→Markdown via trafilatura |
| `indexer.py` | Write Markdown + upload to OpenWebUI RAG |
| `rag_client.py` | OpenWebUI file upload/delete API client |
| `tasks/` | One file per task type — see SPEC per task |

Spec for each module: `modules/<module>/SPEC.md`

---

## Ports

| Port | Service |
| --- | --- |
| 8083 | `api.py` (ingest API) |
| 8080 | llama.cpp (vision captioning) |
| 3000 | OpenWebUI (RAG target) |

---

## Video ingestion DAG

```
download_video
├── describe_single_chunk × N   (one per chunk_duration seconds)
└── download_subtitles
        ├── [subs found]  → index_video  ←─── describe_single_chunk[*]
        └── [no subs]     → extract_audio → transcribe → index_video ←─── describe_single_chunk[*]
```

`index_video` always waits for all chunk tasks regardless of which transcript path was taken. `desc_task_ids` flow from `download_video` output → `download_subtitles` dep_ enrichment → `index_video` dependencies.

## Known issues (open)

- `retriable` tasks have no max retry count — a persistently broken task loops forever on every restart
- Duplicate `download_subtitles` possible if `download_video` re-executes after crash (benign — loser gets CANCELLED)
