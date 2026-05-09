import asyncio
import inspect
from pathlib import Path
from types import SimpleNamespace

from modules.fetcher_url.fetcher_url import slug
from modules.indexer import indexer
from modules.rag_client import rag_client
from modules.tasks.chunk_article import chunk_article
from modules.tasks.download_article import download_article as task_download_article
from modules.tasks.extract_article_content import (
    extract_article_content as task_extract_article_content,
)
from modules.tasks.index_article import index_article as task_index_article
from modules.tasks.summarize_article import summarize_article as task_summarize_article
from modules.tasks.summarize_text_chunk import (
    summarize_text_chunk as task_summarize_text_chunk,
)


class ImmediatePool:
    async def submit(self, fn, label=""):
        result = fn()
        if inspect.isawaitable(result):
            return await result
        return result


class RecordingTaskManager:
    def __init__(self):
        self.created = []

    async def create_task(self, task_type, input_data, dependencies=None):
        task_id = f"{task_type}-{len(self.created) + 1}"
        self.created.append(
            {
                "id": task_id,
                "type": task_type,
                "input_data": input_data,
                "dependencies": dependencies or [],
            }
        )
        return task_id


def rag_config(tmp_path):
    return {
        "paths": {"knowledge_dir": str(tmp_path / "knowledge")},
        "api": {
            "openwebui_base": "http://openwebui.test",
            "openwebui_key": "secret",
            "openwebui_collection": "collection-1",
        },
        "prompts": {
            "text_chunk_summary": {
                "system": "summarize chunk",
                "user_template": "Chunk:\n{text}",
            },
            "article_summary": {
                "system": "summarize article",
                "user_template": "Combined:\n{combined_text}",
            },
        },
    }


def test_indexer_save_and_upload_replaces_existing_entries(tmp_path, monkeypatch):
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    old_file = knowledge_dir / "old.md"
    old_file.write_text("old", encoding="utf-8")
    url = "https://example.com/article"
    url_key = slug(url)
    indexer.save_index(
        knowledge_dir,
        {
            url_key: [
                {
                    "file": str(old_file),
                    "owui_file_id": "old-file-id",
                    "filename": "old.md",
                }
            ]
        },
    )

    uploads = []
    deletes = []

    async def fake_upload(path, config):
        uploads.append((Path(path), config["api"]["openwebui_collection"]))
        return "new-file-id"

    async def fake_delete(file_id, config):
        deletes.append((file_id, config["api"]["openwebui_base"]))

    monkeypatch.setattr(indexer, "upload_to_rag", fake_upload)
    monkeypatch.setattr(rag_client, "delete_file", fake_delete)

    asyncio.run(
        indexer.save_and_upload(
            url,
            "new.md",
            "# New",
            rag_config(tmp_path),
            knowledge_dir,
            replace_existing=True,
        )
    )

    new_file = knowledge_dir / "new.md"
    assert old_file.exists() is False
    assert new_file.read_text(encoding="utf-8") == "# New"
    assert uploads == [(new_file, "collection-1")]
    assert deletes == [("old-file-id", "http://openwebui.test")]
    assert indexer.load_index(knowledge_dir) == {
        url_key: [
            {
                "file": str(new_file),
                "owui_file_id": "new-file-id",
                "filename": "new.md",
            }
        ]
    }


def test_rag_client_upload_polls_and_adds_file_to_collection(tmp_path, monkeypatch):
    path = tmp_path / "article.md"
    path.write_text("content", encoding="utf-8")
    calls = []

    class FakeResponse:
        def __init__(self, payload=None, is_success=True, status_code=200, text="ok"):
            self._payload = payload or {}
            self.is_success = is_success
            self.status_code = status_code
            self.text = text

        def json(self):
            return self._payload

        def raise_for_status(self):
            if not self.is_success:
                raise rag_client.httpx.HTTPStatusError(
                    "bad response", request=SimpleNamespace(), response=SimpleNamespace()
                )

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            calls.append(("client", kwargs))

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, **kwargs):
            calls.append(("post", url, kwargs))
            if url.endswith("/api/v1/files/"):
                uploaded_name = kwargs["files"]["file"][0]
                assert uploaded_name == "article.md"
                return FakeResponse({"id": "file-1"})
            return FakeResponse({})

        async def get(self, url, **kwargs):
            calls.append(("get", url, kwargs))
            return FakeResponse({"data": {"content": "indexed text"}})

    async def fake_sleep(seconds):
        calls.append(("sleep", seconds))

    monkeypatch.setattr(rag_client.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(rag_client.asyncio, "sleep", fake_sleep)

    file_id = asyncio.run(rag_client.upload_to_rag(path, rag_config(tmp_path)))

    assert file_id == "file-1"
    assert ("sleep", 2) in calls
    post_urls = [call[1] for call in calls if call[0] == "post"]
    assert post_urls == [
        "http://openwebui.test/api/v1/files/",
        "http://openwebui.test/api/v1/knowledge/collection-1/file/add",
    ]
    auth_headers = [
        call[2]["headers"]["Authorization"]
        for call in calls
        if call[0] in {"post", "get"}
    ]
    assert set(auth_headers) == {"Bearer secret"}


def test_article_task_pipeline_smoke(tmp_path, monkeypatch):
    async def scenario():
        manager = RecordingTaskManager()
        config = rag_config(tmp_path)
        knowledge_dir = Path(config["paths"]["knowledge_dir"])
        knowledge_dir.mkdir()
        context = {
            "task_manager": manager,
            "download_pool": ImmediatePool(),
            "cpu_pool": ImmediatePool(),
            "config": config,
        }

        async def fake_download_article(url, pool):
            assert url == "https://example.com/article"
            return "<html><article>Body</article></html>"

        monkeypatch.setattr(
            "modules.fetcher_article.fetcher_article.download_article",
            fake_download_article,
        )
        output = await task_download_article.run(
            SimpleNamespace(id="download-1"),
            context,
            {
                "url": "https://example.com/article",
                "url_slug": "abc12345",
                "note": "reader note",
            },
        )

        assert output["html"] == "<html><article>Body</article></html>"
        assert manager.created[-1]["type"] == "extract_article_content"
        assert manager.created[-1]["dependencies"] == ["download-1"]
        assert manager.created[-1]["input_data"]["note"] == "reader note"

        def fake_extract_content(html):
            assert html == "<html><article>Body</article></html>"
            return {"markdown": "Alpha beta gamma", "title": "Example Article"}

        monkeypatch.setattr(
            "modules.parser.parser.extract_content",
            fake_extract_content,
        )
        output = await task_extract_article_content.run(
            SimpleNamespace(id="extract-1"),
            context,
            {
                "url": "https://example.com/article",
                "html": "<html><article>Body</article></html>",
                "url_slug": "abc12345",
            },
        )

        assert output == {"url_slug": "abc12345"}
        assert manager.created[-1]["type"] == "chunk_article"
        assert manager.created[-1]["input_data"]["content"] == "Alpha beta gamma"
        assert manager.created[-1]["input_data"]["title"] == "Example Article"

        output = await chunk_article.run(
            SimpleNamespace(id="chunk-1"),
            context,
            {
                "url": "https://example.com/article",
                "url_slug": "abc12345",
                "title": "Example Article",
                "content": "one two three",
            },
        )

        assert output == {"chunk_count": 1, "task_ids": ["summarize_text_chunk-3"]}
        assert manager.created[-2]["type"] == "summarize_text_chunk"
        assert manager.created[-2]["input_data"] == {
            "text": "one two three",
            "chunk_index": 0,
        }
        assert manager.created[-1]["type"] == "summarize_article"
        assert manager.created[-1]["dependencies"] == ["summarize_text_chunk-3"]

        chat_calls = []

        async def fake_chunk_chat(**kwargs):
            chat_calls.append(kwargs)
            return "chunk summary"

        monkeypatch.setattr(task_summarize_text_chunk, "chat", fake_chunk_chat)
        output = await task_summarize_text_chunk.run(
            SimpleNamespace(id="summary-1"),
            context,
            {"text": "one two three", "chunk_index": 0},
        )

        assert output == {"summary": "chunk summary"}
        assert chat_calls[-1]["prompt"] == "Chunk:\none two three"
        assert chat_calls[-1]["system_prompt"] == "summarize chunk"

        async def fake_article_chat(**kwargs):
            chat_calls.append(kwargs)
            return "final summary"

        monkeypatch.setattr(task_summarize_article, "chat", fake_article_chat)
        output = await task_summarize_article.run(
            SimpleNamespace(id="article-summary-1"),
            context,
            {
                "url": "https://example.com/article",
                "url_slug": "abc12345",
                "title": "Example Article",
                "content": "one two three",
                "dep_1": {"summary": "first"},
                "dep_2": {"summary": "second"},
            },
        )

        assert output == {"url_slug": "abc12345", "summary": "final summary"}
        assert chat_calls[-1]["prompt"] == "Combined:\nfirst\nsecond"
        assert manager.created[-1]["type"] == "index_article"
        assert manager.created[-1]["input_data"]["filename"] == "example_article-abc12345.md"
        assert manager.created[-1]["input_data"]["summary"] == "final summary"

        uploads = []

        async def fake_save_and_upload(
            url,
            filename,
            content,
            upload_config,
            upload_knowledge_dir,
            replace_existing=False,
        ):
            uploads.append(
                {
                    "url": url,
                    "filename": filename,
                    "content": content,
                    "knowledge_dir": upload_knowledge_dir,
                    "replace_existing": replace_existing,
                    "collection": upload_config["api"]["openwebui_collection"],
                }
            )

        monkeypatch.setattr(task_index_article, "save_and_upload", fake_save_and_upload)
        output = await task_index_article.run(
            SimpleNamespace(id="index-1"),
            context,
            {
                "url": "https://example.com/article",
                "url_slug": "abc12345",
                "filename": "ignored-by-current-task.md",
                "title": "Example Article",
                "summary": "final summary",
                "content": "one two three",
            },
        )

        assert output == {
            "url_slug": "abc12345",
            "status": "indexed",
            "filename": "example-article-abc12345.md",
        }
        assert uploads[0]["url"] == "https://example.com/article"
        assert uploads[0]["filename"] == "example-article-abc12345.md"
        assert uploads[0]["knowledge_dir"] == knowledge_dir
        assert uploads[0]["replace_existing"] is True
        assert uploads[0]["collection"] == "collection-1"
        assert uploads[0]["content"].startswith("# Example Article\n\nfinal summary")
        assert "\n\nIngest date: " in uploads[0]["content"]

    asyncio.run(scenario())
