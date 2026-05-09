## Project
`ingest`: Python DAG-based ingestion service for articles, video, and manga.

## Current Focus
Build testing infrastructure one path at a time. Use isolated temp paths and
mocked services; never use production config, production DB, production
knowledge dirs, or private APIs in tests.

## Environment
- Use `nix-shell` from the repo root.
- Prefer local Nix cache `https://cache.box.headpats.uk`; see `AGENTS.md`.
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

## Next Recommended Tests
1. Commit current fetcher smoke test if not already committed.
2. Add indexer/RAG client smoke tests using temp knowledge dirs and mocked
   `httpx` calls.
3. Add task-level smoke tests for article path:
   `download_article -> extract_article_content -> chunk_article ->
   summarize_text_chunk -> summarize_article -> index_article`, with LLM and RAG
   upload mocked.
4. Add video fallback tests later:
   - captions path with mocked subtitle segments
   - no-captions Whisper path using temp DB/dirs and local model path
     `/opt/ai-lab/models/whisper/ggml-medium.bin`
5. Add manga pipeline test later with a mock private API and generated dummy
   images. Include deliberately wrong visible page numbers in images to verify
   prompt behavior asks the model to ignore visual page markings.

## Open Questions
- How strict should semantic/LLM correctness checks be? Candidate approach:
  deterministic mocked LLM for CI-style smoke tests, then optional local-model
  evaluation using embeddings/similarity against reference text for manual or
  slower integration runs.
- Whisper/no-captions video fallback still needs an end-to-end regression case.
