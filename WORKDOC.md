## Project
`ingest`: Python DAG-based ingestion service for articles, video, and manga.

## Current Focus
Build testing infrastructure one path at a time. Use isolated temp paths and
mocked services; never use production config, production DB, production
knowledge dirs, or private APIs in tests. Fast mocked smoke coverage is now in
place for core, fetchers, indexer/RAG, article tasks, video tasks, manga tasks,
and deterministic synthetic fixture generation. Current next path: run and tune
slower endpoint-backed integration tests using generated dummy data.

## Environment
- Use `nix-shell` from the repo root.
- Prefer local Nix cache `https://cache.box.headpats.uk`; see `AGENTS.md`.
- Slower endpoint-backed tests can use host-local services, accounting for the
  sandbox/network boundary:
  - reasoning LLM: `http://localhost:8080`
  - llama-video: `http://localhost:7080`
  - embeddings: `http://localhost:6080`
- Baseline commands:
  - `nix-shell --run 'python -m compileall run_api.py modules'`
  - `nix-shell --run 'pytest tests/test_smoke_core.py tests/test_smoke_fetchers.py'`
  - `git diff --check`

## Completed
- General audit/cleanup completed and committed.
- Prompts moved into `config.example.toml` under `[prompts.*]`.
- `AGENTS.md` added for future agent/session conventions.
- Nix shell added with Python 3.12, pytest, and core runtime deps.
- Core smoke tests added and committed:
  - config loader override isolation
  - URL helpers
  - parser helpers
  - batching helper
  - worker pool
  - temp SQLite `TaskDB`
- Fetcher smoke tests added:
  - `fetcher_video.get_video_metadata`
  - `fetcher_video.download_video`
  - `fetcher_subtitles.download_subtitles`
  - `fetcher_article.download_article`
  - All external I/O mocked; no network or real downloads.
- Indexer/RAG/article smoke tests added and committed:
  - `indexer.save_and_upload` replacement cleanup with temp knowledge dirs
  - `rag_client.upload_to_rag` mocked `httpx` upload/poll/add flow
  - Article task path through download, extract, chunk, summarize, and index
    with parser, LLM, and RAG upload mocked.
- `AGENTS.md` commit convention clarified: the configured git author should not
  be duplicated as a `Co-authored-by` trailer.
- Video task smoke tests added:
  - `download_video` chunk fan-out and subtitle task creation
  - `download_subtitles` captions and no-captions fallback branches
  - `extract_audio` ffmpeg command and `transcribe` Whisper command/deps
  - `summarize_video` and `index_video` dep-output assembly with LLM/RAG mocked
  - Video task specs updated where they had drifted from current behavior.
- Manga smoke tests added:
  - `fetcher_manga.fetch_gallery` mocked API/image downloads and 429 handling
  - `download_manga` overlapping page batch fan-out and index dependency shape
  - `describe_manga_page`, `summarize_manga`, `transcribe_manga`, and
    `index_manga` prompt/data assembly with LLM/RAG mocked
  - Manga fetcher/task specs updated where they had drifted from current behavior.
- Synthetic manga fixture generator added:
  - dependency-free PNG writer and bitmap text renderer under
    `tests/fixtures/synthetic_manga.py`
  - produces three deterministic manga-style pages plus `reference.json`
  - visible page numbers are deliberately wrong (`99`, `7`, `42`) while story
    order is pages 1-3.
- Endpoint-backed manga integration scaffold added:
  - opt-in with `INGEST_RUN_ENDPOINT_TESTS=1`
  - defaults: reasoning LLM `http://localhost:8080`, llama-video
    `http://localhost:7080`
  - override with `INGEST_REASONING_LLM_BASE` and `INGEST_LLAMA_VIDEO_BASE`
  - normal `pytest` collects it as skipped.

## Next Recommended Tests
1. Run the opt-in manga endpoint integration from the actual service network
   context and tune assertions/prompts as needed:
   `INGEST_RUN_ENDPOINT_TESTS=1 pytest tests/integration/test_manga_endpoint_fixture.py`.
2. Add slower no-captions Whisper integration using temp DB/dirs and
   local model path `/opt/ai-lab/models/whisper/ggml-medium.bin`.
3. Add optional semantic assertions using the embeddings endpoint to compare
   generated summaries/transcripts against reference text.

## Open Questions
- How strict should semantic/LLM correctness checks be? Candidate approach:
  deterministic mocked LLM for CI-style smoke tests, then optional local-model
  evaluation using embeddings/similarity against reference text for manual or
  slower integration runs.
- Whisper/no-captions video fallback still needs an end-to-end regression case.
