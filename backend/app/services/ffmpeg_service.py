from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)


class FFmpegError(RuntimeError):
    pass


def _run(args: list[str]) -> subprocess.CompletedProcess:
    logger.debug("Running: %s", " ".join(args))
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise FFmpegError(result.stderr.strip()[-2000:] or "ffmpeg command failed")
    return result


def check_ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def probe_duration(path: Path) -> float:
    args = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "json", str(path),
    ]
    result = _run(args)
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def extract_audio(video_path: Path, audio_path: Path, sample_rate: int = 16000) -> Path:
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    args = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-acodec", "pcm_s16le", "-ar", str(sample_rate), "-ac", "1",
        str(audio_path),
    ]
    _run(args)
    return audio_path


def change_tempo(input_path: Path, output_path: Path, factor: float) -> Path:
    """Time-stretch audio without pitch shift using ffmpeg's atempo chain."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    factor = max(0.5, min(2.0, factor))
    filters = []
    remaining = factor
    # atempo supports only 0.5-2.0 per filter instance; chain if needed.
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    filters.append(f"atempo={remaining:.4f}")
    args = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-filter:a", ",".join(filters),
        str(output_path),
    ]
    _run(args)
    return output_path


def concat_audio_segments(segment_paths: list[Path], output_path: Path) -> Path:
    """Concatenate pre-timed audio segments (already padded with silence) into one track."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    list_file = output_path.with_suffix(".txt")
    list_file.write_text("\n".join(f"file '{p.resolve()}'" for p in segment_paths))
    args = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c", "copy", str(output_path),
    ]
    _run(args)
    list_file.unlink(missing_ok=True)
    return output_path


def generate_silence(duration: float, output_path: Path, sample_rate: int = 24000) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.0, duration)
    args = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"anullsrc=r={sample_rate}:cl=mono",
        "-t", f"{duration:.3f}", str(output_path),
    ]
    _run(args)
    return output_path


def mux_video_audio(video_path: Path, audio_path: Path, output_path: Path) -> Path:
    """Replace the audio track while copying the original video stream (no re-encode)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    args = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(output_path),
    ]
    _run(args)
    return output_path