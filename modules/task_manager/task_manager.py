import asyncio
import json
import logging
import sqlite3
import importlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("task_manager")

class TaskStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class RateLimitError(Exception): pass

@dataclass
class Task:
    id: str
    type: str
    status: TaskStatus
    dependencies: List[str] = field(default_factory=list)
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    error_msg: Optional[str] = None

class TaskDB:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    dependencies TEXT NOT NULL,
                    input_data TEXT NOT NULL,
                    output_data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error_msg TEXT
                )
            """)
            conn.commit()

    def _row_to_task(self, row) -> Task:
        return Task(
            id=row[0],
            type=row[1],
            status=TaskStatus(row[2]),
            dependencies=json.loads(row[3]),
            input_data=json.loads(row[4]),
            output_data=json.loads(row[5]),
            created_at=row[6],
            updated_at=row[7],
            error_msg=row[8]
        )

    async def add_task(self, task: Task) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._add_task_sync, task)

    def _add_task_sync(self, task: Task):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    task.id, task.type, task.status.value,
                    json.dumps(task.dependencies), json.dumps(task.input_data),
                    json.dumps(task.output_data), task.created_at,
                    task.updated_at, task.error_msg
                )
            )
            conn.commit()

    async def get_task(self, task_id: str) -> Optional[Task]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_task_sync, task_id)

    def _get_task_sync(self, task_id: str) -> Optional[Task]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return self._row_to_task(row) if row else None

    async def update_status(self, task_id: str, status: TaskStatus, output: Dict[str, Any] = None, input_data: Dict[str, Any] = None, error: str = None) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._update_status_sync, task_id, status, output, input_data, error)

    def _update_status_sync(self, task_id: str, status: TaskStatus, output: Dict[str, Any], input_data: Dict[str, Any], error: str):
        with sqlite3.connect(self.db_path) as conn:
            out_str = json.dumps(output) if output else None
            in_str = json.dumps(input_data) if input_data else None
            conn.execute(
                "UPDATE tasks SET status = ?, output_data = COALESCE(?, output_data), input_data = COALESCE(?, input_data), error_msg = ?, updated_at = ? WHERE id = ?",
                (status.value, out_str, in_str, error, datetime.now().isoformat(), task_id)
            )
            conn.commit()

    async def get_pending_ready_tasks(self) -> List[Task]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_ready_tasks_sync)

    def _get_ready_tasks_sync(self) -> List[Task]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT t.id FROM tasks t
                WHERE t.status = 'PENDING'
                AND (
                    json_extract(t.input_data, '$.retry_at') IS NULL
                    OR datetime(replace(json_extract(t.input_data, '$.retry_at'), 'T', ' ')) <= datetime('now', 'localtime')
                )
                AND NOT EXISTS (
                    SELECT 1 FROM json_each(t.dependencies) as d
                    JOIN tasks dep ON dep.id = d.value
                    WHERE dep.status != 'DONE'
                )
            """).fetchall()
            return [self._row_to_task(conn.execute("SELECT * FROM tasks WHERE id = ?", (r[0],)).fetchone()) for r in rows]

    async def get_children(self, parent_id: str) -> List[Task]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_children_sync, parent_id)

    def _get_children_sync(self, parent_id: str) -> List[Task]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT t.* FROM tasks t, json_each(t.dependencies) as d
                WHERE d.value = ?
            """, (parent_id,)).fetchall()
            return [self._row_to_task(r) for r in rows]

    async def reset_running_to_pending(self) -> int:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._reset_sync)

    def _reset_sync(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            # RUNNING tasks were interrupted mid-flight — always retry.
            # FAILED tasks whose input marks them as retriable are also reset,
            # covering transient errors (e.g. llama server not ready on startup).
            cursor = conn.execute("""
                UPDATE tasks SET status = 'PENDING', error_msg = NULL
                WHERE status = 'RUNNING'
                OR (status = 'FAILED' AND json_extract(input_data, '$.retriable') = 1)
            """)
            conn.commit()
            return cursor.rowcount

    async def find_task(self, type: str, input_key: str, input_val) -> Optional[Task]:
        """Return an existing task matching type + a specific input field value, or None."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._find_task_sync, type, input_key, input_val)

    def _find_task_sync(self, type: str, input_key: str, input_val) -> Optional[Task]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("""
                SELECT * FROM tasks
                WHERE type = ?
                AND json_extract(input_data, ?) = ?
                AND status NOT IN ('CANCELLED', 'FAILED')
                LIMIT 1
            """, (type, f"$.{input_key}", input_val)).fetchone()
            return self._row_to_task(row) if row else None

    async def get_all_tasks(self) -> List[Task]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_all_sync)

    def _get_all_sync(self) -> List[Task]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
            return [self._row_to_task(r) for r in rows]

    async def delete_tasks_by_identifiers(self, url: str = None, url_slug: str = None) -> int:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._delete_tasks_by_identifiers_sync, url, url_slug)

    def _delete_tasks_by_identifiers_sync(self, url: str = None, url_slug: str = None) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM tasks WHERE (? IS NOT NULL AND json_extract(input_data, '$.url') = ?) OR (? IS NOT NULL AND json_extract(input_data, '$.url_slug') = ?)",
                (url, url, url_slug, url_slug)
            )
            conn.commit()
            return cursor.rowcount

class TaskManager:
    def __init__(self, db_path: Path, worker_pools: Dict[str, Any], config: Dict[str, Any]):
        self.db = TaskDB(db_path)
        self.pools = worker_pools
        self.config = config
        self.running = False
        self._loop_task = None

    async def start(self):
        self.running = True
        reset_count = await self.db.reset_running_to_pending()
        if reset_count > 0:
            log.info(f"[task_manager] reset {reset_count} running tasks to pending")
        self._loop_task = asyncio.create_task(self._main_loop())

    async def stop(self):
        self.running = False
        if self._loop_task:
            self._loop_task.cancel()
            await asyncio.gather(self._loop_task, return_exceptions=True)
            self._loop_task = None

    async def _main_loop(self):
        while self.running:
            try:
                ready_tasks = await self.db.get_pending_ready_tasks()
                if ready_tasks:
                    log.info(
                        "[task_manager] ready tasks: %s",
                        ", ".join(f"{task.type}:{task.id}" for task in ready_tasks),
                    )
                for task in ready_tasks:
                    asyncio.create_task(self._dispatch(task))
                await asyncio.sleep(1)
            except Exception as e:
                log.error(f"[task_manager] loop error: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def _dispatch(self, task: Task):
        log.info(f"[task_manager] dispatching {task.id} ({task.type})")

        loop = asyncio.get_running_loop()
        success = await loop.run_in_executor(None, self._try_lock_task, task.id)
        if not success:
            log.info(f"[task_manager] skipped {task.id} ({task.type}); lock not acquired")
            return

        try:
            module_name = f"modules.tasks.{task.type}.{task.type}"
            module = importlib.import_module(module_name)

            # Context with pools and task_manager
            context = {f"{k}_pool": v for k, v in self.pools.items()}
            context["task_manager"] = self
            context["config"] = self.config

            # Enrich input_data with results from dependencies
            enriched_input = task.input_data.copy()
            for dep_id in task.dependencies:
                dep_task = await self.db.get_task(dep_id)
                if dep_task and dep_task.status == TaskStatus.DONE:
                    enriched_input[f"dep_{dep_id}"] = dep_task.output_data

            pool_name = getattr(module, "POOL", None)
            if pool_name:
                pool = self.pools.get(pool_name)
                if pool:
                    async def run_in_pool() -> None:
                        await self._run_task(task, module, context, enriched_input)

                    log.info(
                        f"[task_manager] submitting {task.id} ({task.type}) to pool={pool_name}"
                    )
                    await pool.submit(
                        run_in_pool,
                        label=f"{task.type}:{task.id}",
                    )
                    return

            await self._run_task(task, module, context, enriched_input)
        except Exception as e:
            await self._fail_task(task, e)

    async def _run_task(
        self,
        task: Task,
        module: Any,
        context: Dict[str, Any],
        enriched_input: Dict[str, Any],
    ) -> None:
        try:
            result = await module.run(task, context, input_data=enriched_input)
            await self.db.update_status(task.id, TaskStatus.DONE, output=result, error=None)
            log.info(f"[task_manager] task {task.id} ({task.type}) completed")
        except RateLimitError as e:
            retry_at = (datetime.now() + timedelta(seconds=60)).isoformat()
            new_input = task.input_data.copy()
            new_input["retry_at"] = retry_at
            await self.db.update_status(
                task.id,
                TaskStatus.PENDING,
                input_data=new_input,
                error=f"Rate limited until {retry_at}: {e}",
            )
            log.warning(
                f"[task_manager] rate limit hit for {task.id} ({task.type}); retry_at={retry_at}: {e}"
            )
        except Exception as e:
            await self._fail_task(task, e)

    async def _fail_task(self, task: Task, exc: Exception) -> None:
        error_summary = self._format_exception(exc)
        log.error(
            f"[task_manager] task {task.id} ({task.type}) failed: {error_summary}",
            exc_info=True,
        )
        await self.db.update_status(task.id, TaskStatus.FAILED, error=error_summary)
        await self._propagate_failure(task.id)

    def _format_exception(self, exc: Exception) -> str:
        message = str(exc).strip()
        if message:
            return f"{type(exc).__name__}: {message}"
        return type(exc).__name__

    def _try_lock_task(self, task_id: str) -> bool:
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.execute("UPDATE tasks SET status = 'RUNNING' WHERE id = ? AND status = 'PENDING'", (task_id,))
            conn.commit()
            return cursor.rowcount > 0

    async def _propagate_failure(self, parent_id: str):
        children = await self.db.get_children(parent_id)
        for child in children:
            log.info(
                f"[task_manager] cancelling child {child.id} ({child.type}) because parent {parent_id} failed"
            )
            await self.db.update_status(
                child.id,
                TaskStatus.CANCELLED,
                error=f"Parent {parent_id} failed",
            )
            await self._propagate_failure(child.id)

    async def create_task(self, type: str, input_data: Dict[str, Any], dependencies: List[str] = None) -> str:
        import uuid
        task_id = str(uuid.uuid4())
        new_task = Task(
            id=task_id,
            type=type,
            status=TaskStatus.PENDING,
            dependencies=dependencies or [],
            input_data=input_data
        )
        await self.db.add_task(new_task)
        return task_id
