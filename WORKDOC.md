## Project
`ingest`: Python DAG-based ingestion service for articles, video, and manga.

## Current Focus
The current test expansion is complete. Fast mocked tests are in place for core
helpers, fetchers, indexer/RAG, article tasks, video tasks, manga tasks, and
synthetic fixture generation. Manga endpoint-backed integration, video Whisper
fallback integration, and llama-video visual integration are in place and
passing.

## Environment Notes
- Use `nix-shell` from the repo root.
- Prefer local Nix cache `https://cache.box.headpats.uk`; see `AGENTS.md`.
- Host-local endpoints are reachable from Codex via both `localhost` and
  `10.0.10.56`:
  - reasoning LLM: `http://localhost:8080`
  - llama-video: `http://localhost:7080`
  - embeddings: `http://localhost:6080`
- `shell.nix` now packages `llama-video` for local tests. The known workaround
  is active: ffmpeg/ffprobe are symlinked into `/tmp/ffbins`, and that directory
  is prepended to `PATH`, because `llama-video` derives ffprobe by replacing
  `ffmpeg` in the path.
- Whisper model for no-captions fallback:
  `/opt/ai-lab/models/whisper/ggml-medium.bin`
- `shell.nix` includes `espeak-ng` for deterministic TTS and `whisper-cpp` for
  local transcription tests.
- Slow video tests may take around 3x the fixture video length.
- Keep generated video fixture resolution at or below 540p because the real
  pipeline downscales chunks to 540p.

## Completed Slow Coverage
- Manga endpoint integration:
  - `INGEST_RUN_ENDPOINT_TESTS=1 pytest tests/integration/test_manga_endpoint_fixture.py -q -s`
  - Passed against default localhost endpoints.
  - Optional embedding assertion also passed with
    `INGEST_USE_EMBEDDING_ASSERTIONS=1`.
- Synthetic manga fixture uses small misleading corner page markings. The real
  page range exists only in the prompt, matching the real scan/page-index issue.
- Synthetic video fixture generation:
  - `tests/fixtures/synthetic_video.py`
  - 6s, 10fps, `960x540`
  - Ria moves toward a blue key; Kai opens a red door
  - espeak-ng TTS says: "Ria sees the blue key. Kai opens the red door."
  - `tests/test_synthetic_video_fixture.py` verifies generation and resolution.
- Video audio/Whisper integration:
  - `INGEST_RUN_ENDPOINT_TESTS=1 pytest tests/integration/test_video_endpoint_fixture.py::test_synthetic_video_audio_transcribes_with_whisper -q -s`
  - Passed with `whisper-cpp` from `shell.nix` and model
    `/opt/ai-lab/models/whisper/ggml-medium.bin`.
- Video visual/llama-video integration:
  - `INGEST_RUN_ENDPOINT_TESTS=1 INGEST_RUN_LLAMA_VIDEO_TEST=1 pytest tests/integration/test_video_endpoint_fixture.py::test_synthetic_video_visual_understanding_with_llama_video -q -s`
  - Passed against `localhost:7080` with a neutral prompt:
    "Describe the visible events in the video."
  - Full video integration file passed:
    `INGEST_RUN_ENDPOINT_TESTS=1 INGEST_RUN_LLAMA_VIDEO_TEST=1 pytest tests/integration/test_video_endpoint_fixture.py -q -s`

## Remaining Tests
- None currently identified. If llama-video output becomes brittle, add optional
  embedding assertions against `http://localhost:6080` comparing the generated
  visual description to the synthetic video reference summary.

## Baseline Verification
- After Python edits:
  - `nix-shell --run 'python -m compileall run_api.py modules'`
  - `nix-shell --run 'pytest'`
  - `git diff --check`

## Current Git Notes
- Last committed test work:
  - `e124494 test: use corner page markings in manga fixture`
  - `bd26836 test: refine manga endpoint assertions`
  - `acc64a6 test: tune synthetic manga fixture`
- Commit convention: use configured git author as commit author; add only
  additional contributors as trailers. For Codex-authored commits include:
  `Co-authored-by: Codex <codex@openai.com>`.
