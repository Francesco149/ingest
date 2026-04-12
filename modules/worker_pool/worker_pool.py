import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable
import logging

log = logging.getLogger("worker_pool")

@dataclass
class Job:
    fn: Callable[[], Any]
    label: str = ""
    future: asyncio.Future = field(default_factory=asyncio.Future)

class WorkerPool:
    def __init__(self, name: str, n_workers: int):
        self.name = name
        self.n_workers = n_workers
        self.queue: asyncio.Queue[Job] = asyncio.Queue()
        self._tasks: list[asyncio.Task] = []

    def start(self):
        for i in range(self.n_workers):
            self._tasks.append(asyncio.create_task(self._worker(i)))
        log.info(f"[pool:{self.name}] {self.n_workers} workers ready")

    async def _worker(self, idx: int):
        while True:
            job = await self.queue.get()
            log.info(f"[pool:{self.name}:{idx}] start: {job.label}")
            try:
                result = await job.fn()
                job.future.set_result(result)
            except Exception as e:
                log.error(f"[pool:{self.name}:{idx}] failed: {job.label} — {e}", exc_info=True)
                job.future.set_exception(e)
            finally:
                self.queue.task_done()
            log.info(f"[pool:{self.name}:{idx}] done: {job.label}")

    async def submit(self, fn: Callable[[], Any], label: str = "") -> Any:
        task_fn = fn
        if not asyncio.iscoroutinefunction(fn):
            loop = asyncio.get_running_loop()
            async def wrapped_fn():
                return await loop.run_in_executor(None, fn)
            task_fn = wrapped_fn

        job = Job(fn=task_fn, label=label,
                  future=asyncio.get_event_loop().create_future())
        await self.queue.put(job)
        return await job.future

    @property
    def depth(self) -> int:
        return self.queue.qsize()
