import asyncio
import os
import shutil
from types import SimpleNamespace

import pytest

from modules.tasks.extract_audio import extract_audio as task_extract_audio
from modules.tasks.transcribe import transcribe as task_transcribe
from tests.test_smoke_video_tasks import ImmediatePool
from tests.fixtures.synthetic_video import generate_synthetic_video_fixture


pytestmark = pytest.mark.skipif(
    os.environ.get("INGEST_RUN_ENDPOINT_TESTS") != "1",
    reason="endpoint-backed tests are opt-in; set INGEST_RUN_ENDPOINT_TESTS=1",
)


def video_config(tmp_path):
    whisper_bin = os.environ.get("INGEST_WHISPER_BIN") or shutil.which("whisper-cli")
    if not whisper_bin:
        pytest.skip("whisper-cli not available")
    whisper_model = os.environ.get(
        "INGEST_WHISPER_MODEL", "/opt/ai-lab/models/whisper/ggml-medium.bin"
    )
    if not os.path.exists(whisper_model):
        pytest.skip(f"Whisper model not available: {whisper_model}")
    return {
        "paths": {
            "knowledge_dir": str(tmp_path / "knowledge"),
            "ffmpeg_bin": shutil.which("ffmpeg") or "ffmpeg",
            "whisper_bin": whisper_bin,
            "whisper_model": whisper_model,
        },
        "api": {
            "llama_base": os.environ.get("INGEST_LLAMA_VIDEO_BASE", "http://localhost:7080"),
            "llama_timeout": 120,
        },
        "processing": {"fps": 2.0},
        "prompts": {
            "video_describe": {
                "user": "Describe the visible events in the video."
            }
        },
    }


def test_synthetic_video_audio_transcribes_with_whisper(tmp_path):
    async def scenario():
        reference = generate_synthetic_video_fixture(tmp_path / "video")
        config = video_config(tmp_path)
        extracted_audio = tmp_path / "extracted.wav"
        context = {
            "config": config,
            "cpu_pool": ImmediatePool(),
            "cuda_pool": ImmediatePool(),
        }

        audio_output = await task_extract_audio.run(
            SimpleNamespace(id="extract-audio"),
            context,
            {
                "video_path": reference["video_path"],
                "audio_path": str(extracted_audio),
                "url_slug": "synthetic-video",
                "desc_task_ids": ["desc-1"],
                "metadata": {"title": "Synthetic Video"},
            },
        )
        assert extracted_audio.exists()
        assert audio_output["audio_path"] == str(extracted_audio)

        transcript_output = await task_transcribe.run(
            SimpleNamespace(id="transcribe"),
            context,
            {
                "url_slug": "synthetic-video",
                "dep_audio": {
                    "audio_path": str(extracted_audio),
                    "desc_task_ids": ["desc-1"],
                    "metadata": {"title": "Synthetic Video"},
                },
            },
        )

        transcript = transcript_output["transcript"].lower()
        assert "blue" in transcript
        assert "key" in transcript
        assert "door" in transcript
        assert transcript_output["desc_task_ids"] == ["desc-1"]

    asyncio.run(scenario())


def test_synthetic_video_visual_understanding_with_llama_video(tmp_path):
    if os.environ.get("INGEST_RUN_LLAMA_VIDEO_TEST") != "1":
        pytest.skip("set INGEST_RUN_LLAMA_VIDEO_TEST=1 to run llama-video visual test")
    pytest.importorskip("llama_video")

    async def scenario():
        from modules.tasks.describe_single_chunk import (
            describe_single_chunk as task_describe_single_chunk,
        )

        reference = generate_synthetic_video_fixture(tmp_path / "video")
        config = video_config(tmp_path)
        output = await task_describe_single_chunk.run(
            SimpleNamespace(id="describe-video"),
            {"config": config},
            {
                "video_path": reference["video_path"],
                "start_ts": 0,
                "end_ts": reference["duration_seconds"],
                "url": "https://example.test/video/synthetic",
                "url_slug": "synthetic-video",
            },
        )

        description = output["description"].lower()
        assert "blue" in description
        assert "key" in description
        assert "red" in description
        assert "door" in description

    asyncio.run(scenario())
