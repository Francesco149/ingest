# worker_pool

## Purpose
Fixed-size async worker pool. Wraps sync callables in `run_in_executor` automatically, queues jobs, and surfaces results or exceptions to the caller.

## Exports
```python
class WorkerPool:
    def __init__(self, name: str, n_workers: int)
    def start() -> None
    async def stop() -> None
    async def submit(fn: Callable, label: str = "") -> Any
    @property depth -> int
    @property active -> int
```

## Imports From
None — no internal dependencies.

## Behavior Rules
- `start()` spawns `n_workers` asyncio tasks running `_worker` loops
- `start()` is idempotent; a second call leaves existing workers in place
- `stop()` cancels worker tasks, waits for them to exit, and clears the worker list
- `submit()` detects sync vs async callable: sync functions are wrapped in `loop.run_in_executor(None, fn)`
- `depth` returns `queue.qsize()` — number of pending (not yet started) jobs
- `active` returns the number of jobs currently running in worker coroutines
- Job future is created with `asyncio.get_event_loop().create_future()`; exceptions are propagated to caller
- Queue/start/done/failure log lines include pool name, job label, active jobs, and queued jobs

## Must NOT
- Import from any internal module
- Block the event loop with sync callables — always use executor for sync work
