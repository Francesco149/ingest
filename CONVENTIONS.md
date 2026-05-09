# CONVENTIONS.md

## Project context

This is the `ingest` service — a DAG-scheduled ingestion pipeline. Before making any change, orient yourself with:

1. `AGENTS.md` — session workflow, repository map, commit rules
2. `DESIGN.md` — architecture, DAG structure, known issues
3. `TECH_SPEC.md` — API contracts, task schemas, config reference
4. `CONVENTIONS.md` — this file; coding style and agentic workflow rules

## Navigating this codebase

**The entry points are small.** `run_api.py` starts uvicorn, `modules/api/api.py`
owns routes, and `modules/engine/engine.py` owns pool/config wiring and ingest
routing. Start there.

**Each task is a standalone file.** To understand any stage of the pipeline, read `tasks/{task_type}.py`. The docstring at the top of every task file specifies:
- Input fields (direct and via dep_ enrichment)
- Output fields
- What child tasks it creates and with what dependencies

**Shared utilities (read-only for tasks):**
- `modules/fetcher_*/*` — source-specific network/download behavior
- `modules/parser/parser.py` — VTT and HTML text extraction
- `modules/indexer/indexer.py` — Markdown write + RAG upload
- `modules/worker_pool/worker_pool.py` — async worker pool (rarely need to touch)
- `modules/task_manager/task_manager.py` — DAG scheduler + SQLite (rarely need to touch)

**Prompt ownership.** All durable LLM prompts live in `config.example.toml` under
`[prompts.*]`. Task code may assemble source material and format configured
templates, but must not own long-lived prompt instructions.

**Specs are contracts, not archives.** When code behavior changes, update the
nearest `SPEC.md` and any affected table/diagram in `DESIGN.md` or `TECH_SPEC.md`
in the same change.

## Task file conventions

Every task file must have a module docstring in this format:
```
Task: {task_type}
Pool: {pool_name} | (none)
Input:
    field_name  type  description
    ...
Input (via dep_ enrichment from {other_task}):
    field_name  type  description
Output:
    field_name  type  description
Creates:
    {task_type}  — description; dep: ...
```

Tasks access their dep outputs like:
```python
dep_val = next(
    (v.get("field") for k, v in input_data.items()
     if k.startswith("dep_") and isinstance(v, dict) and "field" in v),
    fallback,
)
```

Tasks must re-raise exceptions rather than swallowing them — `task_manager` marks the task FAILED and propagates cancellation to children.

## Adding a new task type

1. Create `tasks/{task_type}.py` with the standard docstring and `async def run(task, context, input_data)`.
2. Add or update `modules/tasks/{task_type}/SPEC.md`.
3. Update `DESIGN.md` to show where it fits in the DAG.
4. Update `TECH_SPEC.md § Task types` table.
5. Wire it into the DAG by having an existing task call `task_manager.create_task("{task_type}", ...)` with the right dependencies.

No registration step is needed — `task_manager` imports modules by name dynamically.

## DAG design rules

- **Declare the full DAG upfront.** When a task creates children, create all of them (including grandchildren) so the complete graph is visible in the database immediately. Do not create tasks from within tasks that will themselves create tasks — flatten where possible.
- **Pass data via output/dep_, not input_data pass-through.** If task B needs data from task A, make A a dependency of B and let task_manager inject it as `dep_{A.id}`. Only pass data directly in `input_data` when it's not available as a dep output.
- **Idempotent creation.** If a task spawns children and might be re-executed (e.g. crash between `run()` return and `update_status(DONE)`), use `task_manager.db.find_task()` to check for existing children before creating new ones.
- **Mark retriable tasks.** If a task can fail transiently (e.g. depends on an external server), set `"retriable": True` in `input_data` so it's reset to PENDING on restart.

## Coding style

- Type-hint all `run()` signatures: `async def run(task: Task, context: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]`
- Use `context["key"]` (KeyError on missing) not `context.get("key")` for required pool/config access — fail fast
- Use `input_data.get("key")` for optional fields, `input_data["key"]` for required
- Log with the task-scoped logger: `log = logging.getLogger("task_{name}")`
- Keep subprocess calls synchronous inside `pool.submit()` — don't mix `asyncio.create_subprocess_exec` with worker pool submission
- Keep config loading centralized in `modules/config_loader.py`; avoid fallback
  literals in task code when `config.example.toml` can be the default source.

## Testing

- Use `nix-shell` from the repository root to get Python and system tools.
- Use a local `.venv` inside the Nix shell for Python dependencies from
  `requirements.txt`.
- Run `python -m compileall run_api.py modules` after Python edits.
- Run `pytest` for test changes and before committing behavior changes.
- Run `git diff --check` before finishing.
- Add focused tests when changing DAG behavior or task contracts; the
  Whisper/no-captions fallback especially needs a real integration regression.

## Commit style

- If asked to commit, co-author the commit with all human/agent contributors
  using `Co-authored-by:` trailers.
- Ask for the user's preferred commit identity if it is not already known.
- Include `Co-authored-by: Codex <codex@openai.com>` for Codex-authored work.

## Known sharp edges

- `worker_pool.submit()` wraps sync callables in `run_in_executor` automatically, but async callables are awaited directly in the worker. Don't pass a coroutine object (call it as a lambda).
- `task_manager._main_loop` is single-threaded dispatch — it won't deadlock but won't saturate multiple pool workers in a single tick.
- SQLite's `json_extract` is used in task queries — keep `input_data` values JSON-serialisable (no Python objects, no `None` as dict values unless intentional).
