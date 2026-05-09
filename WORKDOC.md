## Project
`ingest`: Python DAG-based ingestion service for articles, video, and manga.

## Current Focus
Build testing infrastructure one path at a time. Use isolated temp paths and
mocked services; never use production config, production DB, production
knowledge dirs, or private APIs in tests. Current next path after video smoke:
manga pipeline tests with mocked private API and generated dummy images.

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

## Next Recommended Tests
1. Add manga pipeline test with a mock private API and generated dummy
   images. Include deliberately wrong visible page numbers in images to verify
   prompt behavior asks the model to ignore visual page markings.
2. Add slower optional no-captions Whisper integration using temp DB/dirs and
   local model path `/opt/ai-lab/models/whisper/ggml-medium.bin`.

## Open Questions
- How strict should semantic/LLM correctness checks be? Candidate approach:
  deterministic mocked LLM for CI-style smoke tests, then optional local-model
  evaluation using embeddings/similarity against reference text for manual or
  slower integration runs.
- Whisper/no-captions video fallback still needs an end-to-end regression case.
