"""
URL utility functions — no I/O, no subprocesses.
"""

import hashlib
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse


def slug(url: str) -> str:
    """8-char SHA-1 hex digest of the URL — used as stable file identifier."""
    return hashlib.sha1(url.encode()).hexdigest()[:8]


def normalize_url(url: str) -> str:
    """Canonicalize URLs: strip tracking params, normalize YouTube variants."""
    parsed = urlparse(url)

    yt_id = None
    if "youtube.com" in parsed.netloc:
        qs = parse_qs(parsed.query)
        if "v" in qs:
            yt_id = qs["v"][0]
        elif "/shorts/" in parsed.path:
            yt_id = parsed.path.split("/shorts/")[-1].split("/")[0]
    elif "youtu.be" in parsed.netloc:
        yt_id = parsed.path.lstrip("/").split("/")[0]

    if yt_id:
        return f"https://www.youtube.com/watch?v={yt_id}"

    STRIP = {"utm_source", "utm_medium", "utm_campaign", "utm_content",
             "utm_term", "si", "pp", "feature", "ref", "igshid"}
    qs = parse_qs(parsed.query)
    clean = {k: v for k, v in qs.items() if k not in STRIP}
    return urlunparse(parsed._replace(query=urlencode(clean, doseq=True)))


def creator_slug(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def is_video(url: str) -> bool:
    return any(x in url for x in [
        "youtube.com/watch", "youtu.be/", "youtube.com/shorts",
        ".mp4", ".mkv", ".webm", ".mov",
    ])


def is_manga(url: str, fingerprint: str = "manga.net/g/") -> bool:
    return fingerprint in url


def get_manga_id(url: str, fingerprint: str = "manga.net/g/") -> str:
    pattern = re.escape(fingerprint) + r"(\d+)"
    match = re.search(pattern, url)
    return match.group(1) if match else ""
