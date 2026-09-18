from __future__ import annotations

import asyncio
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)


class TTSError(RuntimeError):
    pass


async def _synthesize_async(text: str, voice: str, output_path: Path) -> None:
    try:
        import edge_tts
    except ImportError as exc:
        raise TTSError("edge-tts is not installed") from exc

    communicate = edge_tts.Communicate(text=text, voice=voice)
    try:
        await communicate.save(str(output_path))
    except Exception as exc:
        raise TTSError(f"edge-tts synthesis failed: {exc}") from exc


def synthesize(text: str, voice: str, output_path: Path) -> Path:
    """Synchronous wrapper: renders `text` to `output_path` as an audio file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not text.strip():
        raise TTSError("Cannot synthesize empty text")
    asyncio.run(_synthesize_async(text, voice, output_path))
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise TTSError("edge-tts produced no audio output")
    return output_path
