# task_manager

## Purpose
SQLite-backed DAG scheduler. Owns task creation, status transitions, dispatch locking, dep_ enrichment, and failure propagation.

## Exports
```python
class TaskStatus(Enum):
    PENDING | RUNNING | DONE | FAILED | CANCELLED

class RateLimitError(Exception): pass

@dataclass
class Task:
    id: str
    type: str
    status: TaskStatus
    dependencies: list[str]
    input_data: dict
    output_data: dict
    created_at: str
    updated_at: str
    error_msg: str | None

class TaskDB:
    async def add_task(task: Task)
    async def get_task(task_id: str) -> Task | None
    async def update_status(task_id: str, status: TaskStatus, output: dict = None, input_data: dict = None, error: str = None)
    async def get_pending_ready_tasks() -> list[Task]
    async def get_children(parent_id: str) -> list[Task]
    async def reset_running_to_pending() -> int
    async def find_task(type: str, input_key: str, input_val) -> Task | None
    async def get_all_tasks() -> list[Task]
    async def delete_tasks_by_identifiers(self, url: str = None, url_slug: str = None) -> int

class TaskManager:
    def __init__(self, db_path: Path, worker_pools: dict[str, Any], config: dict[str, Any])
    async def start()
    async def stop()
    async def create_task(type: str, input_data: dict, dependencies: list[str] = None) -> str
```

## Imports From
None — no internal module dependencies (task modules are loaded dynamically via `importlib`).

## Behavior Rules
- On startup: `RUNNING` → `PENDING` (interrupted); `FAILED` with `input_data.retriable == true` → `PENDING`
- Dispatch lock: `UPDATE … WHERE status = 'PENDING'` checked via `rowcount` — prevents double-dispatch
- `_dispatch` enriches `input_data` with `dep_{task_id}: output_data` for each DONE dependency before calling `module.run()`
- `_dispatch` catches `RateLimitError`: sets status `PENDING` and `input_data['retry_at'] = (now + 60s).isoformat()`
- Pooled and unpooled tasks share the same `_run_task` path, so `DONE` / `FAILED` / rate-limited transitions behave the same either way
- Task modules are loaded as `tasks.{task.type}` via `importlib.import_module`
- `TaskManager` stores worker pools separately from config; config is passed explicitly to the constructor
- `context` passed to tasks: `{pool_name}_pool` for each pool, plus `task_manager` and `config`
- `_propagate_failure`: recursively CANCELS all children when a task FAILs
- `_main_loop` polls every 1 second; on exception sleeps 5 seconds before resuming
- `find_task` excludes CANCELLED and FAILED rows
- `get_pending_ready_tasks` only selects `PENDING` tasks where `input_data['retry_at']` is `NULL` or `<= CURRENT_TIMESTAMP`
- Failure records include the exception class name in `error_msg`, and task-manager logs include task IDs and pool routing

## Must NOT
- Import from `engine`, `api`, or any fetcher module
- Hold task business logic — only scheduling and state machine
- Allow two workers to run the same task (dispatch lock enforces this)
