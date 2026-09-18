from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.security import sanitize_filename
from app.models.job import JobStage, TranscriptSegment
from app.services import audio_timeline, downloader, ffmpeg_service, transcriber, translator

logger = get_logger(__name__)

# (stage, progress_percent, message) -> None
StageCallback = Callable[[JobStage, int, str], None]


class PipelineError(RuntimeError):
    pass


@dataclass
class PipelineResult:
    output_path: Path
    source_title: str
    source_language: str
    source_duration: float
    segments: list[TranscriptSegment]


def run_pipeline(
    url: str,
    settings: Settings,
    job_id: str,
    on_stage: Optional[StageCallback] = None,
) -> PipelineResult:
    def report(stage: JobStage, pct: int, msg: str) -> None:
        logger.info("[%s] %s (%s%%)", stage.value, msg, pct)
        if on_stage:
            on_stage(stage, pct, msg)

    if not ffmpeg_service.check_ffmpeg_available():
        raise PipelineError("ffmpeg/ffprobe not found on PATH. Install FFmpeg and try again.")

    work_dir = settings.jobs_dir / job_id
    work_dir.mkdir(parents=True, exist_ok=True)

    # 1. Download
    report(JobStage.DOWNLOADING, 2, "Starting download...")

    def dl_progress(fraction: float, msg: str) -> None:
        report(JobStage.DOWNLOADING, 2 + int(fraction * 18), msg)

    try:
        video_info = downloader.download_video(
            url,
            settings.downloads_dir,
            settings.max_video_duration,
            on_progress=dl_progress,
            cookies_file=settings.cookies_file,
        )
    except downloader.DownloadError as exc:
        raise PipelineError(f"Download failed: {exc}") from exc

    # 2. Extract audio
    report(JobStage.EXTRACTING_AUDIO, 22, "Extracting audio track...")
    audio_path = settings.audio_dir / f"{video_info.video_id}.wav"
    try:
        ffmpeg_service.extract_audio(video_info.file_path, audio_path)
    except ffmpeg_service.FFmpegError as exc:
        raise PipelineError(f"Audio extraction failed: {exc}") from exc

    # 3. Transcribe (+ language detection)
    report(JobStage.TRANSCRIBING, 25, "Transcribing speech...")

    def tr_progress(fraction: float, msg: str) -> None:
        report(JobStage.TRANSCRIBING, 25 + int(fraction * 25), msg)

    try:
        transcription = transcriber.transcribe(
            audio_path, settings.whisper_model, settings.whisper_device, on_progress=tr_progress
        )
    except transcriber.TranscriptionError as exc:
        raise PipelineError(f"Transcription failed: {exc}") from exc

    # 4. Translate
    report(JobStage.TRANSLATING, 50, f"Translating from '{transcription.language}' to English...")

    def tl_progress(fraction: float, msg: str) -> None:
        report(JobStage.TRANSLATING, 50 + int(fraction * 15), msg)

    try:
        translator.translate_segments(
            transcription.segments,
            transcription.language,
            settings.translation_provider,
            settings.translation_model,
            on_progress=tl_progress,
        )
    except translator.TranslationError as exc:
        raise PipelineError(f"Translation failed: {exc}") from exc

    # 5. Synthesize + time-align
    report(JobStage.SYNTHESIZING, 65, "Synthesizing English speech...")
    total_duration = video_info.duration or ffmpeg_service.probe_duration(video_info.file_path)
    dubbed_audio_path = work_dir / "dubbed_audio.mp3"

    def synth_progress(fraction: float, msg: str) -> None:
        report(JobStage.SYNTHESIZING, 65 + int(fraction * 20), msg)

    try:
        audio_timeline.assemble_timeline(
            transcription.segments,
            total_duration,
            settings.tts_voice,
            work_dir / "segments",
            dubbed_audio_path,
            settings.max_speech_rate_factor,
            on_progress=synth_progress,
        )
    except Exception as exc:  # noqa: BLE001 - surfaced to job/CLI as a PipelineError
        raise PipelineError(f"Audio assembly failed: {exc}") from exc

    # 6. Mux final video
    report(JobStage.RENDERING, 90, "Muxing final video (copying original video stream)...")
    safe_title = sanitize_filename(video_info.title) or video_info.video_id
    output_path = settings.output_dir / f"{safe_title}_{job_id}_dubbed.mp4"
    try:
        ffmpeg_service.mux_video_audio(video_info.file_path, dubbed_audio_path, output_path)
    except ffmpeg_service.FFmpegError as exc:
        raise PipelineError(f"Final rendering failed: {exc}") from exc

    report(JobStage.COMPLETED, 100, "Dubbing complete")

    return PipelineResult(
        output_path=output_path,
        source_title=video_info.title,
        source_language=transcription.language,
        source_duration=total_duration,
        segments=transcription.segments,
    )
