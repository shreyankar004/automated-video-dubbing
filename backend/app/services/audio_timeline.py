from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.logging import get_logger
from app.models.job import TranscriptSegment
from app.services import ffmpeg_service, text_normalizer, tts

logger = get_logger(__name__)


@dataclass
class TimedClip:
    segment_index: int
    path: Path
    target_duration: float
    actual_duration: float
    speed_factor: float


def build_segment_audio(
    segment: TranscriptSegment,
    voice: str,
    work_dir: Path,
    max_speed_factor: float,
) -> TimedClip:
    work_dir.mkdir(parents=True, exist_ok=True)
    target_duration = max(0.3, segment.end - segment.start)
    text = text_normalizer.normalize_for_speech(segment.translated_text or segment.text)

    raw_path = work_dir / f"seg_{segment.index:04d}_raw.mp3"
    tts.synthesize(text, voice, raw_path)
    raw_duration = ffmpeg_service.probe_duration(raw_path)

    speed_factor = 1.0
    final_path = raw_path

    if raw_duration > target_duration and raw_duration > 0:
        needed_factor = min(raw_duration / target_duration, max_speed_factor)
        if needed_factor > 1.02:
            sped_path = work_dir / f"seg_{segment.index:04d}_sped.mp3"
            ffmpeg_service.change_tempo(raw_path, sped_path, needed_factor)
            speed_factor = needed_factor
            final_path = sped_path

    actual_duration = ffmpeg_service.probe_duration(final_path)

    if actual_duration < target_duration - 0.05:
        padded_path = work_dir / f"seg_{segment.index:04d}_padded.mp3"
        silence_path = work_dir / f"seg_{segment.index:04d}_silence.mp3"
        ffmpeg_service.generate_silence(target_duration - actual_duration, silence_path)
        ffmpeg_service.concat_audio_segments([final_path, silence_path], padded_path)
        final_path = padded_path
        actual_duration = target_duration

    return TimedClip(
        segment_index=segment.index,
        path=final_path,
        target_duration=target_duration,
        actual_duration=actual_duration,
        speed_factor=speed_factor,
    )


def assemble_timeline(
    segments: list[TranscriptSegment],
    total_duration: float,
    voice: str,
    work_dir: Path,
    output_path: Path,
    max_speed_factor: float,
    on_progress=None,
) -> Path:
    """Renders each segment, inserts leading/inter-segment silence, concatenates."""
    work_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    clips: list[Path] = []
    cursor = 0.0
    total = len(segments) or 1

    for i, segment in enumerate(sorted(segments, key=lambda s: s.start)):
        if segment.start > cursor + 0.05:
            gap = work_dir / f"gap_{segment.index:04d}.mp3"
            ffmpeg_service.generate_silence(segment.start - cursor, gap)
            clips.append(gap)

        clip = build_segment_audio(segment, voice, work_dir, max_speed_factor)
        clips.append(clip.path)
        cursor = segment.start + clip.actual_duration

        if on_progress:
            on_progress((i + 1) / total, f"Synthesized segment {i + 1}/{total}")

    if total_duration > cursor + 0.05:
        tail = work_dir / "gap_tail.mp3"
        ffmpeg_service.generate_silence(total_duration - cursor, tail)
        clips.append(tail)

    ffmpeg_service.concat_audio_segments(clips, output_path)
    return output_path