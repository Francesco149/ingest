import asyncio
import inspect
from pathlib import Path
from types import SimpleNamespace

from modules.tasks.download_subtitles import download_subtitles as task_download_subtitles
from modules.tasks.download_video import download_video as task_download_video
from modules.tasks.extract_audio import extract_audio as task_extract_audio
from modules.tasks.index_video import index_video as task_index_video
from modules.tasks.summarize_video import summarize_video as task_summarize_video
from modules.tasks.transcribe import transcribe as task_transcribe


class ImmediatePool:
    async def submit(self, fn, label=""):
        result = fn()
        if inspect.isawaitable(result):
            return await result
        return result


class FakeTaskDB:
    def __init__(self):
        self.find_results = {}
        self.tasks = {}

    async def find_task(self, task_type, field_name, field_value):
        return self.find_results.get((task_type, field_name, field_value))

    async def get_task(self, task_id):
        return self.tasks.get(task_id)


class RecordingTaskManager:
    def __init__(self):
        self.created = []
        self.db = FakeTaskDB()

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


def video_config(tmp_path):
    return {
        "paths": {
            "knowledge_dir": str(tmp_path / "knowledge"),
            "ffmpeg_bin": "ffmpeg",
            "whisper_bin": "whisper-cli",
            "whisper_model": str(tmp_path / "model.bin"),
        },
        "api": {
            "openwebui_base": "http://openwebui.test",
            "openwebui_key": "secret",
            "openwebui_collection": "collection-1",
            "llama_base": "http://llama.test",
            "llama_timeout": 30,
        },
        "processing": {
            "chunk_duration": 30,
            "fps": 2.0,
        },
        "prompts": {
            "video_summarize": {
                "system": "summarize video",
                "user_template": (
                    "Title: {title}\nTags: {tags}\nTranscript:\n{transcript}\n"
                    "Visual:\n{visual_descriptions}"
                ),
            },
            "video_describe": {"user": "describe video"},
        },
    }


def test_download_video_fans_out_chunks_and_subtitle_task(tmp_path, monkeypatch):
    async def scenario():
        manager = RecordingTaskManager()
        context = {
            "task_manager": manager,
            "download_pool": ImmediatePool(),
            "config": video_config(tmp_path),
        }
        video_path = tmp_path / "downloads" / "video-vid12345.mp4"
        video_path.parent.mkdir()

        async def fake_download_video(url, downloads_dir, url_slug, config, pool):
            assert url == "https://example.com/watch?v=1"
            assert downloads_dir == str(video_path.parent)
            assert url_slug == "vid12345"
            video_path.write_text("video", encoding="utf-8")
            return str(video_path)

        async def fake_get_video_duration(path):
            assert path == str(video_path)
            return 75

        monkeypatch.setattr(
            "modules.fetcher_video.fetcher_video.download_video",
            fake_download_video,
        )
        monkeypatch.setattr("modules.engine.engine.get_video_duration", fake_get_video_duration)

        output = await task_download_video.run(
            SimpleNamespace(id="download-video-1"),
            context,
            {
                "url": "https://example.com/watch?v=1",
                "url_slug": "vid12345",
                "downloads_dir": str(video_path.parent),
                "sub_dir": str(tmp_path / "subs"),
                "meta": {"title": "Video Title"},
            },
        )

        assert output["file_path"] == str(video_path)
        assert output["duration"] == 75
        assert output["desc_task_ids"] == [
            "describe_single_chunk-1",
            "describe_single_chunk-2",
            "describe_single_chunk-3",
        ]
        assert output["sub_task_id"] == "download_subtitles-4"
        assert [task["type"] for task in manager.created] == [
            "describe_single_chunk",
            "describe_single_chunk",
            "describe_single_chunk",
            "download_subtitles",
        ]
        assert [task["input_data"]["start_ts"] for task in manager.created[:3]] == [0, 30, 60]
        assert [task["input_data"]["end_ts"] for task in manager.created[:3]] == [30, 60, 75]
        assert all(task["dependencies"] == ["download-video-1"] for task in manager.created)
        assert manager.created[-1]["input_data"]["desc_task_ids"] == output["desc_task_ids"]
        assert manager.created[-1]["input_data"]["metadata"] == {"title": "Video Title"}

    asyncio.run(scenario())


def test_download_subtitles_creates_caption_and_fallback_branches(tmp_path, monkeypatch):
    async def scenario():
        config = video_config(tmp_path)
        transcript_segments = [{"start": 1.0, "end": 2.0, "text": "caption text"}]

        async def fake_download_subtitles(url, target_dir, url_slug, cfg, pool):
            assert cfg is config
            if url.endswith("with-captions"):
                return transcript_segments, "manual"
            return None

        monkeypatch.setattr(
            "modules.fetcher_subtitles.fetcher_subtitles.download_subtitles",
            fake_download_subtitles,
        )

        captions_manager = RecordingTaskManager()
        captions_context = {
            "task_manager": captions_manager,
            "download_pool": ImmediatePool(),
            "config": config,
        }
        output = await task_download_subtitles.run(
            SimpleNamespace(id="subs-1"),
            captions_context,
            {
                "url": "https://example.com/with-captions",
                "url_slug": "vid12345",
                "target_path": str(tmp_path / "subs"),
                "video_path": str(tmp_path / "video.mp4"),
                "desc_task_ids": ["desc-1", "desc-2"],
                "metadata": {"title": "Video Title"},
            },
        )

        assert output == {
            "transcript": transcript_segments,
            "summarize_task_ids": ["summarize_video-1"],
            "index_task_id": "index_video-2",
            "url_slug": "vid12345",
        }
        assert [task["type"] for task in captions_manager.created] == [
            "summarize_video",
            "index_video",
        ]
        assert captions_manager.created[0]["dependencies"] == ["subs-1", "desc-1", "desc-2"]
        assert captions_manager.created[1]["dependencies"] == [
            "subs-1",
            "summarize_video-1",
            "desc-1",
            "desc-2",
        ]
        assert captions_manager.created[0]["input_data"]["transcript"] == transcript_segments
        assert captions_manager.created[1]["input_data"]["transcript"] == transcript_segments

        fallback_manager = RecordingTaskManager()
        fallback_context = {
            "task_manager": fallback_manager,
            "download_pool": ImmediatePool(),
            "config": config,
        }
        output = await task_download_subtitles.run(
            SimpleNamespace(id="subs-2"),
            fallback_context,
            {
                "url": "https://example.com/no-captions",
                "url_slug": "vid12345",
                "target_path": str(tmp_path / "subs"),
                "video_path": str(tmp_path / "video.mp4"),
                "desc_task_ids": ["desc-1", "desc-2"],
                "metadata": {"title": "Video Title"},
            },
        )

        assert output == {
            "transcript": None,
            "audio_task_id": "extract_audio-1",
            "index_task_id": "index_video-4",
            "url_slug": "vid12345",
        }
        assert [task["type"] for task in fallback_manager.created] == [
            "extract_audio",
            "transcribe",
            "summarize_video",
            "index_video",
        ]
        assert fallback_manager.created[0]["dependencies"] == ["subs-2"]
        assert fallback_manager.created[1]["dependencies"] == ["extract_audio-1"]
        assert fallback_manager.created[2]["dependencies"] == [
            "transcribe-2",
            "desc-1",
            "desc-2",
        ]
        assert fallback_manager.created[3]["dependencies"] == [
            "transcribe-2",
            "summarize_video-3",
            "desc-1",
            "desc-2",
        ]
        assert fallback_manager.created[0]["input_data"]["audio_path"] == str(
            tmp_path / "video.wav"
        )

    asyncio.run(scenario())


def test_extract_audio_and_transcribe_use_configured_commands(tmp_path, monkeypatch):
    async def scenario():
        config = video_config(tmp_path)
        context = {
            "cpu_pool": ImmediatePool(),
            "cuda_pool": ImmediatePool(),
            "config": config,
        }
        calls = []

        def fake_extract_run(cmd, capture_output, check):
            calls.append(("extract", cmd, capture_output, check))
            return SimpleNamespace(returncode=0)

        monkeypatch.setattr(task_extract_audio.subprocess, "run", fake_extract_run)
        output = await task_extract_audio.run(
            SimpleNamespace(id="audio-1"),
            context,
            {
                "video_path": str(tmp_path / "video.mp4"),
                "audio_path": str(tmp_path / "video.wav"),
                "url": "https://example.com/video",
                "url_slug": "vid12345",
                "desc_task_ids": ["desc-1"],
                "metadata": {"title": "Video Title"},
            },
        )

        assert output == {
            "audio_path": str(tmp_path / "video.wav"),
            "url": "https://example.com/video",
            "url_slug": "vid12345",
            "desc_task_ids": ["desc-1"],
            "metadata": {"title": "Video Title"},
        }
        assert calls[-1] == (
            "extract",
            [
                "ffmpeg",
                "-i",
                str(tmp_path / "video.mp4"),
                "-ar",
                "16000",
                "-ac",
                "1",
                "-y",
                str(tmp_path / "video.wav"),
            ],
            True,
            True,
        )

        def fake_whisper_run(cmd, capture_output, text):
            calls.append(("whisper", cmd, capture_output, text))
            out_base = cmd[cmd.index("-of") + 1]
            Path(out_base + ".srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nhello", encoding="utf-8")
            return SimpleNamespace(returncode=0, stderr="")

        monkeypatch.setattr(task_transcribe.subprocess, "run", fake_whisper_run)
        output = await task_transcribe.run(
            SimpleNamespace(id="transcribe-1"),
            context,
            {
                "url_slug": "vid12345",
                "dep_audio": {
                    "audio_path": str(tmp_path / "video.wav"),
                    "desc_task_ids": ["desc-1"],
                    "metadata": {"title": "Video Title"},
                },
            },
        )

        assert output == {
            "url_slug": "vid12345",
            "transcript": "1\n00:00:00,000 --> 00:00:01,000\nhello",
            "desc_task_ids": ["desc-1"],
            "metadata": {"title": "Video Title"},
        }
        whisper_cmd = calls[-1][1]
        assert whisper_cmd[:6] == [
            "whisper-cli",
            "-m",
            str(tmp_path / "model.bin"),
            "-f",
            str(tmp_path / "video.wav"),
            "-osrt",
        ]
        assert whisper_cmd[-3:] == ["--language", "auto", "-ng"]

    asyncio.run(scenario())


def test_summarize_and_index_video_use_dep_outputs(tmp_path, monkeypatch):
    async def scenario():
        manager = RecordingTaskManager()
        manager.db.tasks = {
            "desc-1": SimpleNamespace(
                output_data={
                    "start_ts": 0.0,
                    "end_ts": 30.0,
                    "description": "#### 00:00 - 00:30\n\nVisual one",
                }
            ),
            "desc-2": SimpleNamespace(
                output_data={
                    "start_ts": 30.0,
                    "end_ts": 60.0,
                    "description": "#### 00:30 - 01:00\n\nVisual two",
                }
            ),
        }
        config = video_config(tmp_path)
        knowledge_dir = Path(config["paths"]["knowledge_dir"])
        knowledge_dir.mkdir()
        context = {"task_manager": manager, "config": config}
        chat_calls = []

        async def fake_chat(**kwargs):
            chat_calls.append(kwargs)
            return "reasoned video summary"

        monkeypatch.setattr(task_summarize_video, "chat", fake_chat)
        output = await task_summarize_video.run(
            SimpleNamespace(id="summarize-video-1"),
            context,
            {
                "url_slug": "vid12345",
                "transcript": [
                    {"start": 1.0, "end": 2.0, "text": "first line"},
                    {"start": 31.0, "end": 32.0, "text": "second line"},
                ],
                "meta": {"title": "Video Title", "tags": ["tag"]},
                "desc_task_ids": ["desc-1", "desc-2"],
            },
        )

        assert output == {
            "reasoning_text": "reasoned video summary",
            "url_slug": "vid12345",
            "metadata": {"title": "Video Title", "tags": ["tag"]},
        }
        assert chat_calls[0]["system_prompt"] == "summarize video"
        assert "Title: Video Title" in chat_calls[0]["prompt"]
        assert "[00:01] first line" in chat_calls[0]["prompt"]
        assert "[Visual] #### 00:00 - 00:30" in chat_calls[0]["prompt"]

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

        monkeypatch.setattr(task_index_video, "save_and_upload", fake_save_and_upload)
        output = await task_index_video.run(
            SimpleNamespace(id="index-video-1"),
            {"config": config},
            {
                "url": "https://example.com/video",
                "url_slug": "vid12345",
                "meta": {
                    "title": "Video Title",
                    "uploader": "Uploader",
                    "channel": "Uploader",
                    "upload_date": "20260509",
                    "duration_s": 60,
                    "description": "Source description",
                },
                "dep_summary": {"reasoning_text": "reasoned video summary"},
                "dep_desc_late": {"description": "late visual", "start_ts": 30},
                "dep_desc_early": {"description": "early visual", "start_ts": 0},
                "dep_transcript": {"transcript": "whisper line"},
                "transcript": [{"start": 1.0, "end": 2.0, "text": "caption text"}],
            },
        )

        assert output == {"filename": "Video Title-vid12345.md", "url_slug": "vid12345"}
        assert uploads[0]["url"] == "https://example.com/video"
        assert uploads[0]["filename"] == "Video Title-vid12345.md"
        assert uploads[0]["knowledge_dir"] == knowledge_dir
        assert uploads[0]["replace_existing"] is True
        assert uploads[0]["collection"] == "collection-1"
        content = uploads[0]["content"]
        assert "# Video Title" in content
        assert "- Upload date: 2026-05-09" in content
        assert "- Duration s: 60" in content
        assert "- Channel:" not in content
        assert "## Description\nSource description" in content
        assert "## Video Summary (Reasoned)\n\nreasoned video summary" in content
        assert "- whisper line" in content
        assert "caption text" not in content

    asyncio.run(scenario())
