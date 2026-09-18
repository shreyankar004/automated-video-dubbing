
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.core.logging import configure_logging, set_job_context  # noqa: E402
from app.core.security import InvalidYouTubeURLError, validate_youtube_url  # noqa: E402
from app.models.job import JobStage  # noqa: E402
from app.services.pipeline import PipelineError, run_pipeline  # noqa: E402

STAGE_ORDER = [
    JobStage.DOWNLOADING, JobStage.EXTRACTING_AUDIO, JobStage.TRANSCRIBING,
    JobStage.TRANSLATING, JobStage.SYNTHESIZING, JobStage.RENDERING,
]
STAGE_LABELS = {
    JobStage.DOWNLOADING: "Downloading video",
    JobStage.EXTRACTING_AUDIO: "Extracting audio",
    JobStage.TRANSCRIBING: "Transcribing",
    JobStage.TRANSLATING: "Translating to English",
    JobStage.SYNTHESIZING: "Synthesizing English speech",
    JobStage.RENDERING: "Rendering dubbed video",
}


def _print_stage(stage: JobStage, progress: int, message: str) -> None:
    if stage not in STAGE_LABELS:
        return
    step = STAGE_ORDER.index(stage) + 1
    total = len(STAGE_ORDER)
    print(f"[{step:02d}/{total:02d}] {STAGE_LABELS[stage]}... ({progress}%) {message}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Dub a YouTube video into English.")
    parser.add_argument("url", nargs="?", help="YouTube video URL")
    args = parser.parse_args()

    url = args.url or input("Enter YouTube URL: ").strip()

    try:
        url = validate_youtube_url(url)
    except InvalidYouTubeURLError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    configure_logging()
    settings = get_settings()
    job_id = f"cli{int(time.time())}"
    set_job_context(job_id)

    print(f"Starting dubbing pipeline for: {url}\n")
    start = time.time()

    try:
        result = run_pipeline(url, settings, job_id, on_stage=_print_stage)
    except PipelineError as exc:
        print(f"\nFailed: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelled by user.", file=sys.stderr)
        return 130

    elapsed = time.time() - start
    print("\nCompleted.")
    print(f"Detected language: {result.source_language}")
    print(f"Source duration:   {result.source_duration:.1f}s")
    print(f"Processing time:   {elapsed:.1f}s")
    print(f"Output:            {result.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
