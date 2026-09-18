
from __future__ import annotations

import re
from urllib.parse import urlparse

_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}

_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


class InvalidYouTubeURLError(ValueError):
    """Raised when a URL is not a plausible YouTube video URL."""


def is_youtube_url(url: str) -> bool:
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return False

    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    if host not in _YOUTUBE_HOSTS:
        return False

    if host == "youtu.be":
        return bool(parsed.path.strip("/"))

    if parsed.path not in ("/watch", "/shorts", "/live") and not parsed.path.startswith(("/shorts/", "/live/")):
        return False
    if parsed.path == "/watch":
        return "v=" in parsed.query
    return True


def validate_youtube_url(url: str) -> str:
    url = (url or "").strip()
    if not url or not is_youtube_url(url):
        raise InvalidYouTubeURLError(f"'{url}' is not a valid YouTube video URL")
    return url


def sanitize_filename(name: str, max_length: int = 120) -> str:
    """Strip path separators and unsafe characters, preventing traversal."""
    name = name.replace("/", "_").replace("\\", "_")
    name = name.strip().strip(".")
    name = _UNSAFE_FILENAME_CHARS.sub("_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    if not name:
        name = "file"
    return name[:max_length]
