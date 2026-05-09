import inspect
import json
import sys
import types
from types import SimpleNamespace

from modules.fetcher_article import fetcher_article
from modules.fetcher_subtitles import fetcher_subtitles
from modules.fetcher_video import fetcher_video


class ImmediatePool:
    def __init__(self):
        self.labels = []

    async def submit(self, fn, label=""):
        self.labels.append(label)
        result = fn()
        if inspect.isawaitable(result):
            return await result
        return result


def test_get_video_metadata_builds_yt_dlp_command(monkeypatch):
    calls = []

    def fake_run(cmd, capture_output, text):
        calls.append(cmd)
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "title": "Example video",
                    "uploader": "Uploader",
                    "channel": "Uploader",
                    "upload_date": "20260509",
                    "duration_s": 12,
                    "view_count": 100,
                    "like_count": 10,
                    "description": "x" * 1200,
                    "tags": ["one"],
                    "categories": ["cat"],
                    "comment_count": 3,
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(fetcher_video.subprocess, "run", fake_run)
    config = {
        "paths": {"yt_dlp_bin": "yt-dlp"},
        "processing": {"cookies_from_browser": "firefox"},
    }

    metadata = fetcher_video.get_video_metadata("https://example.com/video", config)

    assert calls == [
        [
            "yt-dlp",
            "--dump-json",
            "--no-playlist",
            "--cookies-from-browser",
            "firefox",
            "https://example.com/video",
        ]
    ]
    assert metadata["title"] == "Example video"
    assert metadata["description"] == "x" * 1000


def test_download_video_tries_formats_and_returns_created_file(tmp_path, monkeypatch):
    calls = []
    video_slug = "abc12345"

    def fake_run(cmd, capture_output, text):
        calls.append(cmd)
        if "--format" in cmd and cmd[cmd.index("--format") + 1] == "bad-format":
            return SimpleNamespace(returncode=1, stdout="", stderr="bad format")
        (tmp_path / f"video-{video_slug}.mp4").write_text("video", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(fetcher_video.subprocess, "run", fake_run)
    config = {
        "paths": {"yt_dlp_bin": "yt-dlp"},
        "processing": {
            "yt_formats": ["bad-format", "good-format"],
            "cookies_from_browser": "",
        },
    }

    result = __import__("asyncio").run(
        fetcher_video.download_video(
            "https://example.com/video",
            str(tmp_path),
            video_slug,
            config,
            pool=ImmediatePool(),
        )
    )

    assert result == str(tmp_path / f"video-{video_slug}.mp4")
    assert [cmd[cmd.index("--format") + 1] for cmd in calls] == [
        "bad-format",
        "good-format",
    ]
    assert all("--output" in cmd for cmd in calls)


def test_download_subtitles_uses_isolated_vtt_directory(tmp_path, monkeypatch):
    fake_module = types.ModuleType("youtube_transcript_api")

    class FakeYouTubeTranscriptApi:
        def fetch(self, video_id):
            raise RuntimeError("force yt-dlp fallback")

    fake_module.YouTubeTranscriptApi = FakeYouTubeTranscriptApi
    monkeypatch.setitem(sys.modules, "youtube_transcript_api", fake_module)

    calls = []
    video_slug = "subslug"

    def fake_run(cmd, capture_output):
        calls.append(cmd)
        output_base = cmd[cmd.index("--output") + 1]
        vtt_path = tmp_path / video_slug / "subs.en.vtt"
        assert output_base == str(tmp_path / video_slug / "subs")
        vtt_path.write_text(
            """WEBVTT

00:00:01.000 --> 00:00:02.000
hello
""",
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(fetcher_subtitles.subprocess, "run", fake_run)
    config = {
        "paths": {"yt_dlp_bin": "yt-dlp"},
        "processing": {"cookies_from_browser": ""},
    }

    result = __import__("asyncio").run(
        fetcher_subtitles.download_subtitles(
            "https://www.youtube.com/watch?v=abcdefghijk",
            str(tmp_path),
            video_slug,
            config,
            pool=ImmediatePool(),
        )
    )

    assert result == ([{"start": 1.0, "end": 2.0, "text": "hello"}], "manual")
    assert calls[0][:4] == ["yt-dlp", "--skip-download", "--write-subs", "--sub-lang"]


def test_download_article_uses_browser_headers(monkeypatch):
    seen = {}

    class FakeResponse:
        text = "<html>ok</html>"

        def raise_for_status(self):
            seen["raised"] = True

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            seen["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url):
            seen["url"] = url
            return FakeResponse()

    monkeypatch.setattr(fetcher_article.httpx, "AsyncClient", FakeAsyncClient)

    html = __import__("asyncio").run(
        fetcher_article.download_article("https://example.com/article", ImmediatePool())
    )

    assert html == "<html>ok</html>"
    assert seen["url"] == "https://example.com/article"
    assert seen["raised"] is True
    assert seen["client_kwargs"]["follow_redirects"] is True
    assert "Mozilla/5.0" in seen["client_kwargs"]["headers"]["User-Agent"]
