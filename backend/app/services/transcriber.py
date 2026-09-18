from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from app.core.logging import get_logger
from app.models.job import TranscriptSegment

logger = get_logger(__name__)

ProgressCallback = Callable[[float, str], None]


class TranscriptionError(RuntimeError):
    pass


@dataclass
class TranscriptionResult:
    language: str
    language_probability: Optional[float]
    segments: list[TranscriptSegment]


def _resolve_device(requested: str) -> tuple[str, str]:
    """Return (device, compute_type) honoring 'auto' by probing for CUDA."""
    if requested == "cpu":
        return "cpu", "int8"
    if requested == "cuda":
        return "cuda", "float16"
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda", "float16"
    except ImportError:
        pass
    return "cpu", "int8"


def transcribe(
    audio_path: Path,
    model_size: str,
    device_preference: str,
    on_progress: Optional[ProgressCallback] = None,
) -> TranscriptionResult:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise TranscriptionError("faster-whisper is not installed") from exc

    device, compute_type = _resolve_device(device_preference)
    logger.info("Loading Whisper model '%s' on %s (%s)", model_size, device, compute_type)

    try:
        model = WhisperModel(model_size, device=device, compute_type=compute_type)
    except Exception as exc:
        raise TranscriptionError(f"Failed to load Whisper model '{model_size}': {exc}") from exc

    try:
        segments_iter, info = model.transcribe(
            str(audio_path),
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=1500, speech_pad_ms=400),
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            compression_ratio_threshold=2.2,
        )
    except Exception as exc:
        raise TranscriptionError(f"Transcription failed: {exc}") from exc

    total_duration = info.duration or 1.0
    segments: list[TranscriptSegment] = []
    for idx, seg in enumerate(segments_iter):
        text = seg.text.strip()
        if not text:
            continue
        segments.append(
            TranscriptSegment(index=idx, start=seg.start, end=seg.end, text=text)
        )
        if on_progress:
            on_progress(min(1.0, seg.end / total_duration), f"Transcribed segment {idx + 1}")

    if not segments:
        raise TranscriptionError("No speech detected in the audio track")

    return TranscriptionResult(
        language=info.language,
        language_probability=getattr(info, "language_probability", None),
        segments=segments,
    )