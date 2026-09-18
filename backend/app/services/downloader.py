from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from app.core.logging import get_logger
from app.core.security import sanitize_filename

logger = get_logger(__name__)

ProgressCallback = Callable[[float, str], None]  # (fraction 0..1, message)


class DownloadError(RuntimeError):
    """Raised when yt-dlp cannot retrieve the requested video."""


@dataclass
class VideoInfo:
    video_id: str
    title: str
    duration: Optional[float]
    uploader: Optional[str]
    thumbnail: Optional[str]
    file_path: Path


def fetch_metadata(url: str, cookies_file: Optional[str] = None) -> dict:
    """Return raw yt-dlp metadata without downloading the media."""
    try:
        import yt_dlp
    except ImportError as exc:  # pragma: no cover - exercised only without the dep installed
        raise DownloadError("yt-dlp is not installed") from exc

    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    if cookies_file and Path(cookies_file).exists():
        opts["cookiefile"] = cookies_file
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as exc:  # yt_dlp raises its own DownloadError subclasses
        raise DownloadError(f"Could not fetch video metadata: {exc}") from exc


def download_video(
    url: str,
    output_dir: Path,
    max_duration: int,
    on_progress: Optional[ProgressCallback] = None,
    cookies_file: Optional[str] = None,
) -> VideoInfo:
    """Download the best mp4-compatible stream for `url` into `output_dir`."""
    try:
        import yt_dlp
    except ImportError as exc:
        raise DownloadError("yt-dlp is not installed") from exc

    output_dir.mkdir(parents=True, exist_ok=True)

    def _hook(status: dict) -> None:
        if not on_progress:
            return
        if status.get("status") == "downloading":
            total = status.get("total_bytes") or status.get("total_bytes_estimate") or 0
            done = status.get("downloaded_bytes") or 0
            fraction = (done / total) if total else 0.0
            on_progress(fraction, "Downloading video...")
        elif status.get("status") == "finished":
            on_progress(1.0, "Download finished, post-processing...")

    opts = {
        "format": "bv*+ba/best",
        "outtmpl": str(output_dir / "%(id)s.%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [_hook],
        "restrictfilenames": True,
    }
    if cookies_file and Path(cookies_file).exists():
        opts["cookiefile"] = cookies_file
        logger.info("Using cookies file for authenticated download: %s", cookies_file)

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            duration = info.get("duration")
            if duration and max_duration and duration > max_duration:
                raise DownloadError(
                    f"Video duration {duration}s exceeds MAX_VIDEO_DURATION={max_duration}s"
                )
            info = ydl.extract_info(url, download=True)
            file_path = Path(ydl.prepare_filename(info))
            if file_path.suffix != ".mp4":
                file_path = file_path.with_suffix(".mp4")
    except DownloadError:
        raise
    except Exception as exc:
        raise DownloadError(f"yt-dlp failed to download the video: {exc}") from exc

    if not file_path.exists():
        raise DownloadError("Download reported success but no output file was found")

    safe_title = sanitize_filename(info.get("title") or info.get("id", "video"))
    logger.info("Downloaded '%s' (%s) to %s", safe_title, info.get("id"), file_path)

    return VideoInfo(
        video_id=info.get("id", "unknown"),
        title=info.get("title", safe_title),
        duration=info.get("duration"),
        uploader=info.get("uploader"),
        thumbnail=info.get("thumbnail"),
        file_path=file_path,
    )
