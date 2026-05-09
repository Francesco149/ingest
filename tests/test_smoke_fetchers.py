import inspect
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

from modules.fetcher_article import fetcher_article
from modules.fetcher_manga import fetcher_manga
from modules.fetcher_subtitles import fetcher_subtitles
from modules.fetcher_video import fetcher_video
from tests.fixtures.synthetic_manga import generate_synthetic_manga_fixture


def manga_fetch_config(tmp_path, image_servers=None):
    return {
        "paths": {"db_path": str(tmp_path / "cache.db")},
        "api": {
            "manga_api_url": "https://manga-api.test/",
            "manga_api_key": "",
        },
        "manga": {
            "image_servers": image_servers or ["fallback-img.test"],
            "image_download_batch_size": 8,
            "image_download_concurrency": 3,
        },
    }


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


def test_fetch_gallery_uses_api_auth_and_downloads_images(tmp_path, monkeypatch):
    calls = []

    class FakeResponse:
        def __init__(self, *, payload=None, content=b"", status_code=200):
            self._payload = payload
            self.content = content
            self.status_code = status_code

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status_code >= 400:
                request = SimpleNamespace()
                response = SimpleNamespace(status_code=self.status_code)
                raise fetcher_manga.httpx.HTTPStatusError(
                    "bad response", request=request, response=response
                )

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            calls.append(("client", kwargs))

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None):
            calls.append(("get", url, headers))
            if url == "https://manga-api.test/galleries/123/":
                return FakeResponse(
                    payload={
                        "title": {"pretty": "Gallery"},
                        "image_servers": ["img-a.test", "img-b.test"],
                        "pages": [{"path": "a.jpg"}, {"path": "b.jpg"}],
                    }
                )
            return FakeResponse(content=f"image:{url}".encode("utf-8"))

    monkeypatch.setattr(fetcher_manga.httpx, "AsyncClient", FakeAsyncClient)
    config = manga_fetch_config(tmp_path)
    config["api"]["manga_api_key"] = "key-1"

    result = __import__("asyncio").run(
        fetcher_manga.fetch_gallery("123", str(tmp_path), config)
    )

    assert result["metadata"]["title"]["pretty"] == "Gallery"
    assert result["image_info"] == [
        {"path": str(tmp_path / "image_000.jpg"), "url": "https://img-a.test/a.jpg"},
        {"path": str(tmp_path / "image_001.jpg"), "url": "https://img-b.test/b.jpg"},
    ]
    assert (tmp_path / "image_000.jpg").read_bytes() == b"image:https://img-a.test/a.jpg"
    assert (tmp_path / "image_001.jpg").read_bytes() == b"image:https://img-b.test/b.jpg"
    assert calls[1] == (
        "get",
        "https://manga-api.test/galleries/123/",
        {"Authorization": "Key key-1"},
    )


def test_fetch_gallery_uses_configured_image_servers_when_metadata_omits_them(
    tmp_path,
    monkeypatch,
):
    requested_urls = []

    class FakeResponse:
        def __init__(self, *, payload=None, content=b"", status_code=200):
            self._payload = payload
            self.content = content
            self.status_code = status_code

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status_code >= 400:
                request = SimpleNamespace()
                response = SimpleNamespace(status_code=self.status_code)
                raise fetcher_manga.httpx.HTTPStatusError(
                    "bad response", request=request, response=response
                )

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None):
            requested_urls.append(url)
            if url == "https://manga-api.test/galleries/123/":
                return FakeResponse(payload={"pages": [{"path": "a.jpg"}]})
            return FakeResponse(content=b"image")

    monkeypatch.setattr(fetcher_manga.httpx, "AsyncClient", FakeAsyncClient)
    config = manga_fetch_config(tmp_path, image_servers=["configured-img.test"])

    result = __import__("asyncio").run(
        fetcher_manga.fetch_gallery("123", str(tmp_path), config)
    )

    assert requested_urls == [
        "https://manga-api.test/galleries/123/",
        "https://configured-img.test/a.jpg",
    ]
    assert result["image_info"] == [
        {
            "path": str(tmp_path / "image_000.jpg"),
            "url": "https://configured-img.test/a.jpg",
        }
    ]


def test_fetch_gallery_downloads_fixture_images_from_page_urls(tmp_path, monkeypatch):
    fixture = generate_synthetic_manga_fixture(tmp_path / "fixture")
    requested_urls = []

    class FakeResponse:
        def __init__(self, *, payload=None, content=b"", status_code=200):
            self._payload = payload
            self.content = content
            self.status_code = status_code

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status_code >= 400:
                request = SimpleNamespace()
                response = SimpleNamespace(status_code=self.status_code)
                raise fetcher_manga.httpx.HTTPStatusError(
                    "bad response", request=request, response=response
                )

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None):
            requested_urls.append(url)
            if url == "https://manga-api.test/galleries/synthetic-manga-001/":
                return FakeResponse(
                    payload={
                        "title": {"pretty": fixture["title"]},
                        "image_servers": ["fixture-images.test"],
                        "pages": [
                            {"path": f"story_page_{idx + 1:02d}.png"}
                            for idx in range(len(fixture["image_paths"]))
                        ],
                    }
                )

            page_name = url.rsplit("/", 1)[-1]
            fixture_path = tmp_path / "fixture" / page_name
            return FakeResponse(content=fixture_path.read_bytes())

    monkeypatch.setattr(fetcher_manga.httpx, "AsyncClient", FakeAsyncClient)
    config = manga_fetch_config(tmp_path)

    result = __import__("asyncio").run(
        fetcher_manga.fetch_gallery(
            "synthetic-manga-001",
            str(tmp_path / "downloaded"),
            config,
        )
    )

    assert requested_urls == [
        "https://manga-api.test/galleries/synthetic-manga-001/",
        "https://fixture-images.test/story_page_01.png",
        "https://fixture-images.test/story_page_02.png",
        "https://fixture-images.test/story_page_03.png",
    ]
    assert [info["url"] for info in result["image_info"]] == requested_urls[1:]
    for idx, fixture_path in enumerate(fixture["image_paths"]):
        downloaded_path = tmp_path / "downloaded" / f"image_{idx:03d}.jpg"
        assert result["image_info"][idx]["path"] == str(downloaded_path)
        assert downloaded_path.read_bytes() == Path(fixture_path).read_bytes()


def test_fetch_gallery_caches_successful_metadata_api_response(tmp_path, monkeypatch):
    requested_urls = []

    class FakeResponse:
        def __init__(self, *, payload=None, content=b"", status_code=200):
            self._payload = payload
            self.content = content
            self.status_code = status_code

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status_code >= 400:
                request = SimpleNamespace()
                response = SimpleNamespace(status_code=self.status_code)
                raise fetcher_manga.httpx.HTTPStatusError(
                    "bad response", request=request, response=response
                )

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None):
            requested_urls.append(url)
            if url == "https://manga-api.test/galleries/123/":
                return FakeResponse(
                    payload={
                        "image_servers": ["img.test"],
                        "pages": [{"path": "a.jpg"}],
                    }
                )
            return FakeResponse(content=f"image:{url}".encode("utf-8"))

    monkeypatch.setattr(fetcher_manga.httpx, "AsyncClient", FakeAsyncClient)
    config = manga_fetch_config(tmp_path)

    first = __import__("asyncio").run(
        fetcher_manga.fetch_gallery("123", str(tmp_path / "first"), config)
    )
    second = __import__("asyncio").run(
        fetcher_manga.fetch_gallery("123", str(tmp_path / "second"), config)
    )

    assert first["metadata"] == second["metadata"]
    assert requested_urls == [
        "https://manga-api.test/galleries/123/",
        "https://img.test/a.jpg",
        "https://img.test/a.jpg",
    ]


def test_fetch_gallery_maps_image_429_to_rate_limit(tmp_path, monkeypatch):
    class FakeResponse:
        def __init__(self, *, payload=None, status_code=200):
            self._payload = payload
            self.content = b""
            self.status_code = status_code

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status_code >= 400:
                request = SimpleNamespace()
                response = SimpleNamespace(status_code=self.status_code)
                raise fetcher_manga.httpx.HTTPStatusError(
                    "bad response", request=request, response=response
                )

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None):
            if url.endswith("/galleries/123/"):
                return FakeResponse(
                    payload={
                        "image_servers": ["img.test"],
                        "pages": [{"path": "limited.jpg"}],
                    }
                )
            return FakeResponse(status_code=429)

    monkeypatch.setattr(fetcher_manga.httpx, "AsyncClient", FakeAsyncClient)
    config = manga_fetch_config(tmp_path)

    try:
        __import__("asyncio").run(
            fetcher_manga.fetch_gallery("123", str(tmp_path), config)
        )
    except fetcher_manga.RateLimitError:
        pass
    else:
        raise AssertionError("expected RateLimitError")


def test_fetch_gallery_rate_limit_stops_before_later_page_batches(tmp_path, monkeypatch):
    requested_urls = []

    class FakeResponse:
        def __init__(self, *, payload=None, status_code=200):
            self._payload = payload
            self.content = b""
            self.status_code = status_code

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status_code >= 400:
                request = SimpleNamespace()
                response = SimpleNamespace(status_code=self.status_code)
                raise fetcher_manga.httpx.HTTPStatusError(
                    "bad response", request=request, response=response
                )

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None):
            requested_urls.append(url)
            if url == "https://manga-api.test/galleries/123/":
                return FakeResponse(
                    payload={
                        "image_servers": ["img.test"],
                        "pages": [
                            {"path": "limited.jpg"},
                            {"path": "should-not-request.jpg"},
                            {"path": "also-should-not-request.jpg"},
                        ],
                    }
                )
            return FakeResponse(status_code=429)

    monkeypatch.setattr(fetcher_manga.httpx, "AsyncClient", FakeAsyncClient)
    config = manga_fetch_config(tmp_path)
    config["manga"]["image_download_batch_size"] = 1
    config["manga"]["image_download_concurrency"] = 1

    try:
        __import__("asyncio").run(
            fetcher_manga.fetch_gallery("123", str(tmp_path), config)
        )
    except fetcher_manga.RateLimitError:
        pass
    else:
        raise AssertionError("expected RateLimitError")

    assert requested_urls == [
        "https://manga-api.test/galleries/123/",
        "https://img.test/limited.jpg",
    ]
