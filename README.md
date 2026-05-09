# ingest

Personal DAG-scheduled ingestion service for turning videos, articles, and
manga into Markdown knowledge files and OpenWebUI RAG entries.

> This code was mainly written with AI assistance and is a personal ad hoc
> tool. Review it before adapting it for production.

## Quick Start

Use the Nix shell for development, tests, and agent work:

```bash
nix-shell
python -m compileall run_api.py modules
pytest
python run_api.py
```

The API listens on the configured `server.port` from `config.toml`; the example
config uses port `8083`.

Submit content:

```bash
curl -X POST http://localhost:8083/ingest \
  -H 'content-type: application/json' \
  -d '{"url":"https://example.com/article","note":"optional context"}'
```

Useful API calls:

```bash
curl http://localhost:8083/status
curl http://localhost:8083/tasks
curl http://localhost:8083/knowledge
curl -X POST http://localhost:8083/rerun/index_video
curl -X POST http://localhost:8083/force \
  -H 'content-type: application/json' \
  -d '{"url":"https://example.com/article"}'
```

## Configuration

Copy `config.example.toml` to `config.toml` or set `INGEST_CONFIG` to another
config path. Keep durable prompt text under `[prompts.*]` in config rather than
inside task code.

Important local services and tools:

| Service/tool | Default |
| --- | --- |
| Ingest API | `http://localhost:8083` |
| Reasoning/vision LLM | `http://localhost:8080` |
| OpenWebUI | `http://localhost:3000` |
| Whisper model | `/opt/ai-lab/models/whisper/ggml-medium.bin` |

## Environment

This repo is developed on NixOS. `shell.nix` is the source of truth for agent
and project tooling; add missing Python packages or binaries there first.
`requirements.txt` exists for humans and non-Nix environments that cannot use
the Nix shell.

The shell includes Python, pytest, ffmpeg/ffprobe, yt-dlp, whisper-cpp,
espeak-ng, and the packaged `llama_video` module.

## Docs

- `AGENTS.md` - agent workflow, repo map, commit rules
- `CONVENTIONS.md` - coding conventions and DAG rules
- `DESIGN.md` - architecture and DAG shape
- `TECH_SPEC.md` - API, task, config, and persistence contracts
- `TESTING.md` - baseline checks, slow endpoint tests, synthetic fixtures

## Repository Map

- `run_api.py` starts uvicorn for `modules.api.api:app`.
- `modules/api/api.py` owns FastAPI routes and lifespan.
- `modules/engine/engine.py` owns config, pool wiring, ffprobe, and ingest routing.
- `modules/task_manager/task_manager.py` owns SQLite task state and DAG dispatch.
- `modules/fetcher_*/*` owns source-specific download and fetch behavior.
- `modules/tasks/<task_type>/<task_type>.py` owns one DAG task each.
- `modules/indexer/indexer.py` and `modules/rag_client/rag_client.py` own
  Markdown persistence and OpenWebUI upload/delete behavior.
