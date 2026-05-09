# AGENTS.md

This repository is the `ingest` service: a Python DAG-scheduled ingestion
pipeline for videos, articles, and manga. Start every session by reading:

1. `AGENTS.md` — agent workflow, repository map, commit rules
2. `CONVENTIONS.md` — coding conventions and DAG rules
3. `DESIGN.md` — architecture and DAG shape
4. `TECH_SPEC.md` — API/config/task contract reference
5. `TESTING.md` — test commands, endpoint-backed integration tests, fixtures

Keep docs close to code. If behavior changes, update the smallest authoritative
doc in the same change. Prefer module `SPEC.md` files for module-specific
contracts and `TECH_SPEC.md` only for cross-module/API/config contracts.

## Session Workflow

- Check `git status --short` before edits. Treat existing changes as user work.
- Read the relevant module and its `SPEC.md` before changing behavior.
- Keep prompts in `config.example.toml` under `[prompts.*]`; task code should
  format configured templates, not own prompt text.
- Keep task `POOL` constants, task docstrings, module specs, and
  `TECH_SPEC.md § Task types` aligned.
- Run a focused verification before finishing. At minimum, run
  `python -m compileall run_api.py modules` after Python edits.
- Update `WORKDOC.md` only for active audit notes or unresolved decisions. Do not
  let it become a second spec.

## Testing Environment

This repo is developed on NixOS. Use the repo-local `shell.nix` for a predictable
Python/tooling baseline:

```bash
nix-shell
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m compileall run_api.py modules
```

If `direnv` is enabled, `.envrc` runs `use nix` automatically after
`direnv allow`. Keep `.venv/` untracked.

On NixOS, Python virtualenvs that install binary wheels may need runtime
library patching; `github:GuillaumeDesforges/fix-python` is a known option.
For `llama-video`, prefer the service flake/package definition rather than a
repo-local venv install.

Prefer the local Nix cache when realizing shells or test dependencies:
`https://cache.box.headpats.uk`. It is resolved on the local network via
`10.0.10.1` to `10.0.10.53`.

Additional caches that may be useful:

```text
extra-substituters = https://nix-community.cachix.org
extra-substituters = https://cache.nixos-cuda.org
extra-substituters = https://cache.numtide.com
trusted-public-keys = nix-community.cachix.org-1:mB9FSh9qf2dCimDSUo8Zy7bkq5CX+/rkCWyvRCYg3Fs=
extra-trusted-public-keys = cache.nixos-cuda.org:74DUi4Ye579gUqzH4ziL9IyiJBlDpMRn9MBN8oNan9M=
extra-trusted-public-keys = cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY=
extra-trusted-public-keys = niks3.numtide.com-1:DTx8wZduET09hRmMtKdQDxNNthLQETkc/yaX7M4qK0g=
```

Baseline checks for Python edits:

- `python -m compileall run_api.py modules`
- `pytest`
- `git diff --check`

See `TESTING.md` for endpoint-backed integration tests, synthetic fixtures, and
local model/endpoint defaults.

## Commit Convention

When asked to commit, use the configured git author as the commit author. Add
`Co-authored-by` trailers only for additional contributors that are not already
the commit author.

```text
Co-authored-by: Codex <codex@openai.com>
```

If a human co-author beyond the configured git author is required and their
preferred name/email is unknown, ask before committing. Do not invent a human
email. Keep commit messages short and behavior-focused.

## Code Map

- `run_api.py` starts uvicorn for `modules.api.api:app`.
- `modules/api/api.py` owns FastAPI routes and lifespan.
- `modules/engine/engine.py` owns config, pool wiring, ffprobe, and ingest
  routing. Do not put processing logic there.
- `modules/task_manager/task_manager.py` owns SQLite task state, dependency
  enrichment, and dispatch.
- `modules/worker_pool/worker_pool.py` owns async worker queues.
- `modules/fetcher_*/*` owns source-specific network/download behavior.
- `modules/parser/parser.py` owns VTT and article parsing.
- `modules/indexer/indexer.py` and `modules/rag_client/rag_client.py` own
  Markdown persistence and OpenWebUI upload/delete behavior.
- `modules/tasks/<task_type>/<task_type>.py` owns one DAG task each.

## Current DAG Summary

Video:
`download_video -> describe_single_chunk[] + download_subtitles ->`
`index_video` when subtitles exist, or `extract_audio -> transcribe -> index_video`
when subtitles are unavailable.

Article:
`download_article -> extract_article_content -> chunk_article ->`
`summarize_text_chunk[] -> summarize_article -> index_article`.

Manga:
`download_manga -> describe_manga_page[] -> summarize_manga[] ->`
`transcribe_manga[] -> index_manga`.
