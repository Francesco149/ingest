import asyncio
from datetime import datetime, timedelta

from modules import config_loader
from modules.fetcher_url.fetcher_url import (
    creator_slug,
    get_manga_id,
    is_video,
    normalize_url,
    slug,
)
from modules.parser.parser import _parse_vtt, recursive_split
from modules.task_manager.task_manager import Task, TaskDB, TaskStatus
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
            for worker in pool._tasks:
                worker.cancel()
            await asyncio.gather(*pool._tasks, return_exceptions=True)

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
