from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.core.security import is_youtube_url


class CreateJobRequest(BaseModel):
    url: str = Field(..., description="A YouTube video URL")

    @field_validator("url")
    @classmethod
    def url_must_be_youtube(cls, value: str) -> str:
        if not is_youtube_url(value):
            raise ValueError("url must be a valid YouTube video URL")
        return value.strip()


class CreateJobResponse(BaseModel):
    job_id: str
    status: str


class SegmentOut(BaseModel):
    index: int
    start: float
    end: float
    text: str
    translated_text: Optional[str] = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    stage: str
    progress: int
    message: str
    source_url: str
    source_language: Optional[str] = None
    source_title: Optional[str] = None
    source_duration: Optional[float] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class JobResultResponse(BaseModel):
    job_id: str
    status: str
    output_available: bool
    output_filename: Optional[str] = None
    source_language: Optional[str] = None
    source_duration: Optional[float] = None
    segment_count: int


class TranscriptResponse(BaseModel):
    job_id: str
    source_language: Optional[str]
    segments: list[SegmentOut]


class HealthResponse(BaseModel):
    status: str
    whisper_model: str
    tts_provider: str
    translation_provider: str
