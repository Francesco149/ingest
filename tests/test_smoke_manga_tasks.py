import asyncio
import base64
import sys
import types
from pathlib import Path
from types import SimpleNamespace

fake_cv2 = types.ModuleType("cv2")
fake_cv2.imread = lambda path: None
fake_cv2.imwrite = lambda path, img: False
sys.modules.setdefault("cv2", fake_cv2)

from modules.tasks.describe_manga_page import describe_manga_page as task_describe_manga
from modules.tasks.download_manga import download_manga as task_download_manga
from modules.tasks.index_manga import index_manga as task_index_manga
from modules.tasks.summarize_manga import summarize_manga as task_summarize_manga
from modules.tasks.transcribe_manga import transcribe_manga as task_transcribe_manga


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ"
    "l8nF0GQAAAABJRU5ErkJggg=="
)


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


def manga_config(tmp_path):
    return {
        "paths": {"knowledge_dir": str(tmp_path / "knowledge")},
        "api": {
            "openwebui_base": "http://openwebui.test",
            "openwebui_key": "secret",
            "openwebui_collection": "collection-1",
            "reasoning_llama_base": "http://llm.test",
        },
        "manga": {
            "description_batch_size": 2,
            "description_overlap": 1,
            "summary_max_batch_size": 2,
            "vision_max_tokens": 2048,
            "vision_temperature": 0.2,
            "transcription_max_tokens": 4096,
        },
        "prompts": {
            "manga_describe": {
                "system": "describe manga",
                "user_template": "Describe pages {start}-{end}; ignore visible page numbers.",
            },
            "manga_summarize": {
                "system": "summarize manga",
                "instructions": "focus on semantic retrieval",
                "user_template": (
                    "Title: {title}\nTags: {tags}\nInstructions: {instructions}\n"
                    "Pages:\n{content_body}"
                ),
            },
            "manga_transcribe": {
                "system": "transcribe manga",
                "instructions": "extract dialogue",
                "user_template": (
                    "Reasoning:\n{reasoning_text}\nTitle: {title}\nTags: {tags}\n"
                    "Instructions: {instructions}\nPages:\n{content_body}"
                ),
            },
        },
    }


def manga_metadata():
    return {
        "title": {
            "japanese": "",
            "pretty": "Pretty Manga",
            "english": "English Manga",
        },
        "tags": [{"name": "tag-a"}, {"name": "tag-b"}],
    }


def test_download_manga_fans_out_overlapping_batches_and_index(tmp_path, monkeypatch):
    async def scenario():
        manager = RecordingTaskManager()
        context = {
            "task_manager": manager,
            "config": manga_config(tmp_path),
        }
        page_paths = [str(tmp_path / f"page-{idx}.jpg") for idx in range(4)]

        async def fake_fetch_gallery(gallery_id, download_dir, config):
            assert gallery_id == "gallery-1"
            assert download_dir == tmp_path / "downloads" / "manga123"
            return {
                "metadata": manga_metadata(),
                "image_info": [
                    {"path": path, "url": f"https://img.test/{idx}.jpg"}
                    for idx, path in enumerate(page_paths)
                ],
            }

        monkeypatch.setattr(task_download_manga, "fetch_gallery", fake_fetch_gallery)

        output = await task_download_manga.run(
            SimpleNamespace(id="download-manga-1"),
            context,
            {
                "gallery_id": "gallery-1",
                "download_dir": str(tmp_path / "downloads"),
                "url": "https://example.test/g/gallery-1",
                "url_slug": "manga123",
                "note": "note",
            },
        )

        assert output["gallery_id"] == "gallery-1"
        assert output["image_paths"] == page_paths
        assert output["metadata"] == manga_metadata()
        assert output["desc_task_ids"] == [
            "describe_manga_page-1",
            "describe_manga_page-2",
            "describe_manga_page-3",
        ]
        assert output["transcribe_task_ids"] == [
            "transcribe_manga-5",
            "transcribe_manga-7",
        ]
        assert [task["type"] for task in manager.created] == [
            "describe_manga_page",
            "describe_manga_page",
            "describe_manga_page",
            "summarize_manga",
            "transcribe_manga",
            "summarize_manga",
            "transcribe_manga",
            "index_manga",
        ]
        assert [task["input_data"]["image_paths"] for task in manager.created[:3]] == [
            page_paths[0:2],
            page_paths[1:3],
            page_paths[2:4],
        ]
        assert [(task["input_data"]["start_page"], task["input_data"]["end_page"]) for task in manager.created[:3]] == [
            (1, 2),
            (2, 3),
            (3, 4),
        ]
        assert manager.created[3]["dependencies"] == [
            "describe_manga_page-1",
            "describe_manga_page-2",
        ]
        assert manager.created[4]["dependencies"] == ["summarize_manga-4"]
        assert manager.created[5]["dependencies"] == ["describe_manga_page-3"]
        assert manager.created[6]["dependencies"] == ["summarize_manga-6"]
        assert manager.created[7]["type"] == "index_manga"
        assert manager.created[7]["dependencies"] == [
            "transcribe_manga-5",
            "transcribe_manga-7",
        ]

    asyncio.run(scenario())


def test_manga_llm_tasks_format_prompts_and_index_outputs(tmp_path, monkeypatch):
    async def scenario():
        config = manga_config(tmp_path)
        knowledge_dir = Path(config["paths"]["knowledge_dir"])
        knowledge_dir.mkdir()
        image_path = tmp_path / "page.png"
        image_path.write_bytes(PNG_BYTES)
        chat_calls = []

        async def fake_describe_chat(**kwargs):
            chat_calls.append(kwargs)
            return "Page 1 has visible printed number 99, but story page is first."

        monkeypatch.setattr(task_describe_manga, "chat", fake_describe_chat)
        output = await task_describe_manga.run(
            SimpleNamespace(id="describe-1"),
            {"config": config},
            {
                "image_paths": [str(image_path)],
                "url": "https://example.test/g/gallery-1",
                "url_slug": "manga123",
                "start_page": 1,
                "end_page": 1,
            },
        )

        assert output["url_slug"] == "manga123"
        assert output["descriptions"] == [
            {
                "description": "Page 1 has visible printed number 99, but story page is first.",
                "start_page": 1,
                "end_page": 1,
                "url": "https://example.test/g/gallery-1",
                "url_slug": "manga123",
            }
        ]
        describe_prompt = chat_calls[-1]["prompt"]
        assert describe_prompt[0]["role"] == "system"
        assert describe_prompt[0]["content"] == "describe manga"
        assert describe_prompt[1]["content"][0]["text"] == (
            "Describe pages 1-1; ignore visible page numbers."
        )
        assert describe_prompt[1]["content"][1]["image_url"]["url"].startswith(
            "data:image/png;base64,"
        )

        async def fake_summary_chat(**kwargs):
            chat_calls.append(kwargs)
            return "semantic manga summary"

        monkeypatch.setattr(task_summarize_manga, "chat", fake_summary_chat)
        output = await task_summarize_manga.run(
            SimpleNamespace(id="summarize-1"),
            {"config": config},
            {
                "url_slug": "manga123",
                "metadata": manga_metadata(),
                "dep_late": {
                    "descriptions": [
                        {
                            "description": "second window",
                            "start_page": 3,
                            "end_page": 4,
                            "url": "u",
                            "url_slug": "manga123",
                        }
                    ]
                },
                "dep_early": {
                    "descriptions": [
                        {
                            "description": "first window",
                            "start_page": 1,
                            "end_page": 2,
                            "url": "u",
                            "url_slug": "manga123",
                        }
                    ]
                },
            },
        )

        assert output == {
            "reasoning_text": "semantic manga summary",
            "start_page": 1,
            "url_slug": "manga123",
            "descriptions": [
                {
                    "description": "first window",
                    "start_page": 1,
                    "end_page": 2,
                    "url": "u",
                    "url_slug": "manga123",
                },
                {
                    "description": "second window",
                    "start_page": 3,
                    "end_page": 4,
                    "url": "u",
                    "url_slug": "manga123",
                },
            ],
        }
        assert chat_calls[-1]["system_prompt"] == "summarize manga"
        assert "Title: Pretty Manga" in chat_calls[-1]["prompt"]
        assert "Tags: tag-a, tag-b" in chat_calls[-1]["prompt"]
        assert chat_calls[-1]["prompt"].index("first window") < chat_calls[-1]["prompt"].index(
            "second window"
        )

        async def fake_transcribe_chat(**kwargs):
            chat_calls.append(kwargs)
            return "A: dialogue"

        monkeypatch.setattr("modules.llm_openai.chat", fake_transcribe_chat)
        output = await task_transcribe_manga.run(
            SimpleNamespace(id="transcribe-1"),
            {"config": config},
            {
                "url_slug": "manga123",
                "metadata": manga_metadata(),
                "dep_summary": {
                    "reasoning_text": "semantic manga summary",
                    "descriptions": [
                        {
                            "description": "second window",
                            "start_page": 3,
                            "end_page": 4,
                        },
                        {
                            "description": "first window",
                            "start_page": 1,
                            "end_page": 2,
                        },
                    ],
                },
            },
        )

        assert output == {
            "transcript_text": "A: dialogue",
            "reasoning_text": "semantic manga summary",
            "start_page": 1,
            "url_slug": "manga123",
        }
        assert chat_calls[-1]["system_prompt"] == "transcribe manga"
        assert chat_calls[-1]["max_tokens"] == 4096
        assert chat_calls[-1]["prompt"].index("first window") < chat_calls[-1]["prompt"].index(
            "second window"
        )

        uploads = []

        async def fake_save_and_upload(
            url,
            filename,
            content,
            config,
            knowledge_dir,
            replace_existing=False,
        ):
            uploads.append(
                {
                    "url": url,
                    "filename": filename,
                    "content": content,
                    "knowledge_dir": knowledge_dir,
                    "replace_existing": replace_existing,
                    "collection": config["api"]["openwebui_collection"],
                }
            )

        monkeypatch.setattr(task_index_manga, "save_and_upload", fake_save_and_upload)
        output = await task_index_manga.run(
            SimpleNamespace(id="index-1"),
            {"config": config},
            {
                "gallery_id": "gallery-1",
                "metadata": manga_metadata(),
                "url_slug": "manga123",
                "url": "https://example.test/g/gallery-1",
                "dep_late": {
                    "reasoning_text": "late reasoning",
                    "transcript_text": "late transcript",
                    "start_page": 5,
                },
                "dep_early": {
                    "reasoning_text": "early reasoning",
                    "transcript_text": "early transcript",
                    "start_page": 1,
                },
            },
        )

        assert output == {"filename": "Pretty Manga-manga123.md", "url_slug": "manga123"}
        assert uploads == [
            {
                "url": "https://example.test/g/gallery-1",
                "filename": "Pretty Manga-manga123.md",
                "content": (
                    "early reasoning\n\n---\n\nlate reasoning\n\n"
                    "early transcript\n\n---\n\nlate transcript"
                ),
                "knowledge_dir": knowledge_dir,
                "replace_existing": True,
                "collection": "collection-1",
            }
        ]

    asyncio.run(scenario())
