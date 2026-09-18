
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class JobStage(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    EXTRACTING_AUDIO = "extracting_audio"
    TRANSCRIBING = "transcribing"
    TRANSLATING = "translating"
    SYNTHESIZING = "synthesizing"
    ASSEMBLING_AUDIO = "assembling_audio"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TranscriptSegment:
    index: int
    start: float
    end: float
    text: str
    translated_text: Optional[str] = None


@dataclass
class Job:
    source_url: str
    job_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: JobStatus = JobStatus.QUEUED
    stage: JobStage = JobStage.QUEUED
    progress: int = 0
    message: str = "Queued"
    source_language: Optional[str] = None
    source_title: Optional[str] = None
    source_duration: Optional[float] = None
    output_path: Optional[str] = None
    error: Optional[str] = None
    segments: list[TranscriptSegment] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def update(self, *, stage: JobStage, progress: int, message: str) -> None:
        self.stage = stage
        self.progress = max(0, min(100, progress))
        self.message = message
        if stage not in (JobStage.COMPLETED, JobStage.FAILED):
            self.status = JobStatus.PROCESSING
        self.touch()

    def mark_completed(self, output_path: str) -> None:
        self.status = JobStatus.COMPLETED
        self.stage = JobStage.COMPLETED
        self.progress = 100
        self.message = "Dubbing complete"
        self.output_path = output_path
        self.touch()

    def mark_failed(self, error: str) -> None:
        self.status = JobStatus.FAILED
        self.stage = JobStage.FAILED
        self.message = "Processing failed"
        self.error = error
        self.touch()
