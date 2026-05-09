import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable
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
        self._active_jobs = 0

    def start(self):
        if self._tasks:
            log.info(f"[pool:{self.name}] start skipped; workers already running")
            return
        for i in range(self.n_workers):
            self._tasks.append(asyncio.create_task(self._worker(i)))
        log.info(f"[pool:{self.name}] {self.n_workers} workers ready")

    async def stop(self) -> None:
        if not self._tasks:
            return
        for worker in self._tasks:
            worker.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        log.info(f"[pool:{self.name}] workers stopped")

    async def _worker(self, idx: int):
        while True:
            job = await self.queue.get()
            self._active_jobs += 1
            log.info(
                f"[pool:{self.name}:{idx}] start: {job.label} "
                f"(active={self._active_jobs}, queued={self.depth})"
            )
            try:
                result = await job.fn()
                job.future.set_result(result)
            except Exception as e:
                log.error(f"[pool:{self.name}:{idx}] failed: {job.label} — {e}", exc_info=True)
                job.future.set_exception(e)
            finally:
                self._active_jobs -= 1
                self.queue.task_done()
            log.info(
                f"[pool:{self.name}:{idx}] done: {job.label} "
                f"(active={self._active_jobs}, queued={self.depth})"
            )

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
        log.info(
            f"[pool:{self.name}] queued: {label} "
            f"(active={self._active_jobs}, queued={self.depth})"
        )
        return await job.future

    @property
    def depth(self) -> int:
        return self.queue.qsize()

    @property
    def active(self) -> int:
        return self._active_jobs
