import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace

from modules import config_loader
from modules.task_manager import task_manager as task_manager_module
from modules.fetcher_url.fetcher_url import (
    creator_slug,
    get_manga_id,
    is_video,
    normalize_url,
    slug,
)
from modules.parser.parser import _parse_vtt, recursive_split
from modules.task_manager.task_manager import RateLimitError, Task, TaskDB, TaskManager, TaskStatus
from modules.tasks.utils import get_batches
from modules.worker_pool.worker_pool import WorkerPool


def test_config_loader_merges_test_override(tmp_path, monkeypatch):
    config_path = tmp_path / "config.toml"
    db_path = tmp_path / "ingest-test.db"
    knowledge_dir = tmp_path / "knowledge"
    config_path.write_text(
        f"""
[paths]
db_path = "{db_path}"
knowledge_dir = "{knowledge_dir}"

[workers]
cpu = 1
""",
        encoding="utf-8",
    )

    monkeypatch.setenv("INGEST_CONFIG", str(config_path))
    monkeypatch.setattr(config_loader, "_config", None)

    config = config_loader.get_config()

    assert config["paths"]["db_path"] == str(db_path)
    assert config["paths"]["knowledge_dir"] == str(knowledge_dir)
    assert config["workers"]["cpu"] == 1
    assert "prompts" in config

    monkeypatch.setattr(config_loader, "_config", None)


def test_fetcher_url_helpers_are_stable():
    assert normalize_url("https://youtu.be/abcdefghijk?si=tracker") == (
        "https://www.youtube.com/watch?v=abcdefghijk"
    )
    assert normalize_url("https://example.com/a?utm_source=x&keep=1") == (
        "https://example.com/a?keep=1"
    )
    assert slug("https://example.com/a") == slug("https://example.com/a")
    assert creator_slug("Some Creator!!") == "some-creator"
    assert is_video("https://example.com/file.webm")
    assert get_manga_id("https://example.test/g/12345/read", "example.test/g/") == "12345"


def test_parser_vtt_and_split_helpers():
    vtt = """WEBVTT

00:00:01.000 --> 00:00:03.000
<c>Hello</c>
world

00:00:04.000 --> 00:00:05.500
Again
"""

    assert _parse_vtt(vtt) == [
        {"start": 1.0, "end": 3.0, "text": "Hello world"},
        {"start": 4.0, "end": 5.5, "text": "Again"},
    ]
    chunks = recursive_split("alpha beta gamma delta", max_chars=10, separators=[" "])
    assert all(len(chunk) <= 10 for chunk in chunks)
    assert " ".join(chunks) == "alpha beta gamma delta"


def test_task_utils_batches_are_balanced():
    assert get_batches([], 3) == []
    assert get_batches([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]


def test_worker_pool_runs_sync_and_async_jobs():
    async def scenario():
        pool = WorkerPool("test", 1)
        pool.start()
        try:
            sync_result = await pool.submit(lambda: 21 * 2, label="sync")

            async def async_job():
                await asyncio.sleep(0)
                return "ok"

            async_result = await pool.submit(async_job, label="async")
            assert sync_result == 42
            assert async_result == "ok"
            assert pool.depth == 0
        finally:
            await pool.stop()

    asyncio.run(scenario())


def test_task_db_uses_temp_sqlite_and_dependency_readiness(tmp_path):
    async def scenario():
        db = TaskDB(tmp_path / "tasks.db")
        parent = Task(
            id="parent",
            type="download_article",
            status=TaskStatus.PENDING,
            input_data={"url": "https://example.com/a", "url_slug": "abc"},
        )
        child = Task(
            id="child",
            type="extract_article_content",
            status=TaskStatus.PENDING,
            dependencies=["parent"],
            input_data={"url_slug": "abc"},
        )

        await db.add_task(parent)
        await db.add_task(child)

        ready = await db.get_pending_ready_tasks()
        assert [task.id for task in ready] == ["parent"]

        await db.update_status("parent", TaskStatus.DONE, output={"html": "<p>ok</p>"})
        ready = await db.get_pending_ready_tasks()
        assert [task.id for task in ready] == ["child"]

        found = await db.find_task("download_article", "url_slug", "abc")
        assert found and found.id == "parent"

        retry_at = (datetime.now() - timedelta(seconds=1)).isoformat()
        await db.update_status(
            "child",
            TaskStatus.FAILED,
            input_data={"url_slug": "abc", "retriable": True, "retry_at": retry_at},
            error="temporary",
        )
        assert await db.reset_running_to_pending() == 1
        assert (await db.get_task("child")).status == TaskStatus.PENDING

    asyncio.run(scenario())


def test_task_manager_dispatches_same_pool_tasks_in_parallel(tmp_path, monkeypatch):
    async def scenario():
        pool = WorkerPool("cpu", 2)
        pool.start()
        manager = TaskManager(tmp_path / "tasks.db", {"cpu": pool}, {})
        started = []
        both_started = asyncio.Event()
        release = asyncio.Event()

        async def fake_run(task, context, input_data):
            started.append(task.id)
            if len(started) == 2:
                both_started.set()
            await both_started.wait()
            await release.wait()
            return {"task_id": task.id}

        fake_module = SimpleNamespace(POOL="cpu", run=fake_run)

        def fake_import_module(name):
            if name == "modules.tasks.fake_parallel.fake_parallel":
                return fake_module
            raise AssertionError(f"unexpected module import: {name}")

        monkeypatch.setattr(task_manager_module.importlib, "import_module", fake_import_module)

        try:
            await manager.db.add_task(
                Task(id="task-a", type="fake_parallel", status=TaskStatus.PENDING)
            )
            await manager.db.add_task(
                Task(id="task-b", type="fake_parallel", status=TaskStatus.PENDING)
            )
            ready = await manager.db.get_pending_ready_tasks()
            dispatches = [asyncio.create_task(manager._dispatch(task)) for task in ready]

            await asyncio.wait_for(both_started.wait(), timeout=1.0)
            assert started == ["task-a", "task-b"] or started == ["task-b", "task-a"]

            release.set()
            await asyncio.gather(*dispatches)
            assert (await manager.db.get_task("task-a")).status == TaskStatus.DONE
            assert (await manager.db.get_task("task-b")).status == TaskStatus.DONE
        finally:
            await pool.stop()

    asyncio.run(scenario())


def test_task_manager_resets_pooled_rate_limited_tasks_to_pending(tmp_path, monkeypatch):
    async def scenario():
        pool = WorkerPool("download", 1)
        pool.start()
        manager = TaskManager(tmp_path / "tasks.db", {"download": pool}, {})

        async def fake_run(task, context, input_data):
            raise RateLimitError("slow down")

        fake_module = SimpleNamespace(POOL="download", run=fake_run)

        def fake_import_module(name):
            if name == "modules.tasks.fake_rate_limited.fake_rate_limited":
                return fake_module
            raise AssertionError(f"unexpected module import: {name}")

        monkeypatch.setattr(task_manager_module.importlib, "import_module", fake_import_module)

        try:
            await manager.db.add_task(
                Task(id="task-rate", type="fake_rate_limited", status=TaskStatus.PENDING)
            )
            task = await manager.db.get_task("task-rate")
            await manager._dispatch(task)

            updated = await manager.db.get_task("task-rate")
            assert updated.status == TaskStatus.PENDING
            assert "retry_at" in updated.input_data
            assert updated.error_msg.startswith("Rate limited until ")
        finally:
            await pool.stop()

    asyncio.run(scenario())


def test_task_manager_dispatches_different_pools_concurrently(tmp_path, monkeypatch):
    async def scenario():
        cpu_pool = WorkerPool("cpu", 1)
        vision_pool = WorkerPool("vision", 1)
        cpu_pool.start()
        vision_pool.start()
        manager = TaskManager(
            tmp_path / "tasks.db",
            {"cpu": cpu_pool, "vision": vision_pool},
            {},
        )
        started = set()
        both_started = asyncio.Event()
        release = asyncio.Event()

        async def fake_run(task, context, input_data):
            started.add(task.id)
            if len(started) == 2:
                both_started.set()
            await both_started.wait()
            await release.wait()
            return {"task_id": task.id}

        modules = {
            "modules.tasks.fake_cpu.fake_cpu": SimpleNamespace(POOL="cpu", run=fake_run),
            "modules.tasks.fake_vision.fake_vision": SimpleNamespace(POOL="vision", run=fake_run),
        }

        def fake_import_module(name):
            if name in modules:
                return modules[name]
            raise AssertionError(f"unexpected module import: {name}")

        monkeypatch.setattr(task_manager_module.importlib, "import_module", fake_import_module)

        try:
            await manager.db.add_task(Task(id="task-cpu", type="fake_cpu", status=TaskStatus.PENDING))
            await manager.db.add_task(
                Task(id="task-vision", type="fake_vision", status=TaskStatus.PENDING)
            )
            ready = await manager.db.get_pending_ready_tasks()
            dispatches = [asyncio.create_task(manager._dispatch(task)) for task in ready]

            await asyncio.wait_for(both_started.wait(), timeout=1.0)
            assert started == {"task-cpu", "task-vision"}

            release.set()
            await asyncio.gather(*dispatches)
            assert (await manager.db.get_task("task-cpu")).status == TaskStatus.DONE
            assert (await manager.db.get_task("task-vision")).status == TaskStatus.DONE
        finally:
            await asyncio.gather(cpu_pool.stop(), vision_pool.stop())

    asyncio.run(scenario())


def test_task_manager_leaves_tasks_running_when_pool_is_full(tmp_path, monkeypatch):
    async def scenario():
        pool = WorkerPool("cpu", 1)
        pool.start()
        manager = TaskManager(tmp_path / "tasks.db", {"cpu": pool}, {})
        first_started = asyncio.Event()
        release = asyncio.Event()

        async def fake_run(task, context, input_data):
            if task.id == "task-1":
                first_started.set()
                await release.wait()
            return {"task_id": task.id}

        fake_module = SimpleNamespace(POOL="cpu", run=fake_run)

        def fake_import_module(name):
            if name == "modules.tasks.fake_serial.fake_serial":
                return fake_module
            raise AssertionError(f"unexpected module import: {name}")

        monkeypatch.setattr(task_manager_module.importlib, "import_module", fake_import_module)

        try:
            await manager.db.add_task(Task(id="task-1", type="fake_serial", status=TaskStatus.PENDING))
            await manager.db.add_task(Task(id="task-2", type="fake_serial", status=TaskStatus.PENDING))
            ready = await manager.db.get_pending_ready_tasks()
            dispatches = [asyncio.create_task(manager._dispatch(task)) for task in ready]

            await asyncio.wait_for(first_started.wait(), timeout=1.0)
            await asyncio.sleep(0.05)

            first = await manager.db.get_task("task-1")
            second = await manager.db.get_task("task-2")
            assert first.status == TaskStatus.RUNNING
            assert second.status == TaskStatus.RUNNING
            assert pool.active == 1
            assert pool.depth == 1

            release.set()
            await asyncio.gather(*dispatches)
            assert (await manager.db.get_task("task-1")).status == TaskStatus.DONE
            assert (await manager.db.get_task("task-2")).status == TaskStatus.DONE
            assert pool.active == 0
            assert pool.depth == 0
        finally:
            await pool.stop()

    asyncio.run(scenario())
