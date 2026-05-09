import asyncio
import math
import os
import sys
import types
from types import SimpleNamespace

import httpx
import pytest

from tests.fixtures.synthetic_manga import generate_synthetic_manga_fixture


pytestmark = pytest.mark.skipif(
    os.environ.get("INGEST_RUN_ENDPOINT_TESTS") != "1",
    reason="endpoint-backed tests are opt-in; set INGEST_RUN_ENDPOINT_TESTS=1",
)


def endpoint_config(tmp_path):
    return {
        "paths": {"knowledge_dir": str(tmp_path / "knowledge")},
        "api": {
            "reasoning_llama_base": os.environ.get(
                "INGEST_REASONING_LLM_BASE", "http://localhost:8080"
            ),
            "llama_timeout": 120,
        },
        "manga": {
            "vision_max_tokens": 2048,
            "vision_temperature": 0.2,
            "transcription_max_tokens": 4096,
        },
        "prompts": {
            "manga_describe": {
                "system": (
                    "You describe synthetic manga pages for an ingestion regression test. "
                    "Use page indices from the prompt, not small corner page markings. "
                    "Do not mention visual page markings."
                ),
                "user_template": (
                    "Describe image pages {start}-{end}. These prompt page indices are "
                    "the ground truth. Small corner page numbers printed on the image "
                    "may be deliberately wrong; ignore those visual page markings and "
                    "do not mention them in your answer. "
                    "Capture captions, dialogue, and major actions."
                ),
            },
            "manga_summarize": {
                "system": "Summarize manga page descriptions for semantic retrieval.",
                "instructions": (
                    "Preserve the prompt-provided page order. Do not treat small corner "
                    "page markings as canonical page order, and do not mention those "
                    "visual markings."
                ),
                "user_template": (
                    "Title: {title}\nTags: {tags}\nInstructions: {instructions}\n"
                    "Descriptions:\n{content_body}"
                ),
            },
            "manga_transcribe": {
                "system": "Transcribe manga dialogue from descriptions.",
                "instructions": "Return dialogue in story order.",
                "user_template": (
                    "Reasoning:\n{reasoning_text}\nTitle: {title}\nTags: {tags}\n"
                    "Instructions: {instructions}\nDescriptions:\n{content_body}"
                ),
            },
        },
    }


async def embedding_similarity(expected: str, actual: str) -> float:
    base = os.environ.get("INGEST_EMBEDDINGS_BASE", "http://localhost:6080")
    model = os.environ.get("INGEST_EMBEDDINGS_MODEL", "nomic-embed-text-v1.5.f16.gguf")
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{base.rstrip('/')}/v1/embeddings",
            json={"model": model, "input": [expected, actual]},
        )
    response.raise_for_status()
    data = response.json()["data"]
    left = data[0]["embedding"]
    right = data[1]["embedding"]
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    return dot / (left_norm * right_norm)


def test_generated_manga_fixture_against_local_llm_endpoints(tmp_path, monkeypatch):
    async def scenario():
        fake_cv2 = types.ModuleType("cv2")
        fake_cv2.imread = lambda path: None
        fake_cv2.imwrite = lambda path, img: False
        sys.modules.setdefault("cv2", fake_cv2)

        from modules.llm_openai import chat as real_chat
        from modules.tasks.describe_manga_page import (
            describe_manga_page as task_describe_manga,
        )
        from modules.tasks.summarize_manga import summarize_manga as task_summarize_manga
        from modules.tasks.transcribe_manga import transcribe_manga as task_transcribe_manga

        fixture = generate_synthetic_manga_fixture(tmp_path / "synthetic_manga")
        config = endpoint_config(tmp_path)
        vision_base = os.environ.get("INGEST_LLAMA_VIDEO_BASE", "http://localhost:7080")

        async def vision_chat(**kwargs):
            return await real_chat(**kwargs, base_url=vision_base)

        monkeypatch.setattr(task_describe_manga, "chat", vision_chat)

        description = await task_describe_manga.run(
            SimpleNamespace(id="describe-synthetic"),
            {"config": config},
            {
                "image_paths": fixture["image_paths"],
                "url": fixture["url"],
                "url_slug": fixture["url_slug"],
                "metadata": {
                    "title": {"pretty": fixture["title"]},
                    "tags": [{"name": tag} for tag in fixture["tags"]],
                },
                "start_page": 1,
                "end_page": len(fixture["image_paths"]),
            },
        )

        summary = await task_summarize_manga.run(
            SimpleNamespace(id="summarize-synthetic"),
            {"config": config},
            {
                "url_slug": fixture["url_slug"],
                "metadata": {
                    "title": {"pretty": fixture["title"]},
                    "tags": [{"name": tag} for tag in fixture["tags"]],
                },
                "dep_describe": description,
            },
        )

        transcript = await task_transcribe_manga.run(
            SimpleNamespace(id="transcribe-synthetic"),
            {"config": config},
            {
                "url_slug": fixture["url_slug"],
                "metadata": {
                    "title": {"pretty": fixture["title"]},
                    "tags": [{"name": tag} for tag in fixture["tags"]],
                },
                "dep_summary": summary,
            },
        )

        combined = (
            description["descriptions"][0]["description"]
            + "\n"
            + summary["reasoning_text"]
            + "\n"
            + transcript["transcript_text"]
        ).lower()

        assert description["descriptions"][0]["description"].strip()
        assert summary["reasoning_text"].strip()
        assert transcript["transcript_text"].strip()
        assert "key" in combined
        assert "door" in combined
        assert "star" in combined
        assert "99" not in combined
        assert "42" not in combined

        if os.environ.get("INGEST_USE_EMBEDDING_ASSERTIONS") == "1":
            expected = "\n".join(fixture["expected_summary_points"])
            actual = summary["reasoning_text"] + "\n" + transcript["transcript_text"]
            similarity = await embedding_similarity(expected, actual)
            assert similarity >= float(os.environ.get("INGEST_EMBEDDING_MIN_SIMILARITY", "0.65"))

    asyncio.run(scenario())
