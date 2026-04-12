# api

## Purpose
FastAPI routes and lifespan management. Delegates all logic to engine and task_manager.

## Exports
FastAPI `app` instance (consumed by uvicorn on port from `config["server"]["port"]`).

## Imports From
- `engine`: all pools, task_manager, KNOWLEDGE_DIR, handler functions
- `fetcher_url`: `is_video`, `is_manga`

## Behavior Rules
- Uses `@asynccontextmanager lifespan` pattern — not deprecated `@app.on_event`
- `POST /ingest`: delegates to engine.handle_ingest()
- `GET /status`: reads pool `.n_workers` and `.depth` from engine singletons
- `GET /tasks`: returns id, type, status, created_at, error for all tasks
- `GET /knowledge`: lists `*.md` files in KNOWLEDGE_DIR sorted by mtime descending
- `GET or POST /rerun/{task_type}`: Resets all `DONE` tasks of `task_type` to `PENDING`.
- `POST /force`: Accepts `{"url": "..."}` in body; cleans up data and restarts ingestion.

## Must NOT
- Contain any business logic beyond routing
- Import from fetcher_video, fetcher_subtitles, task_manager, or any task module directly
