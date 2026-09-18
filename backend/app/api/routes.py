from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.schemas.job import (
    CreateJobRequest,
    CreateJobResponse,
    HealthResponse,
    JobResultResponse,
    JobStatusResponse,
    SegmentOut,
    TranscriptResponse,
)
from app.workers.job_manager import get_job_manager

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        whisper_model=settings.whisper_model,
        tts_provider=settings.tts_provider,
        translation_provider=settings.translation_provider,
    )


@router.post("/jobs", response_model=CreateJobResponse, status_code=201)
def create_job(payload: CreateJobRequest) -> CreateJobResponse:
    settings = get_settings()
    manager = get_job_manager(settings)
    job = manager.create_job(payload.url)
    return CreateJobResponse(job_id=job.job_id, status=job.status.value)


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str) -> JobStatusResponse:
    settings = get_settings()
    manager = get_job_manager(settings)
    job = manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        stage=job.stage.value,
        progress=job.progress,
        message=job.message,
        source_url=job.source_url,
        source_language=job.source_language,
        source_title=job.source_title,
        source_duration=job.source_duration,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("/jobs/{job_id}/result", response_model=JobResultResponse)
def get_job_result(job_id: str) -> JobResultResponse:
    settings = get_settings()
    manager = get_job_manager(settings)
    job = manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResultResponse(
        job_id=job.job_id,
        status=job.status.value,
        output_available=bool(job.output_path),
        output_filename=job.output_path.split("/")[-1] if job.output_path else None,
        source_language=job.source_language,
        source_duration=job.source_duration,
        segment_count=len(job.segments),
    )


@router.get("/jobs/{job_id}/transcript", response_model=TranscriptResponse)
def get_transcript(job_id: str) -> TranscriptResponse:
    settings = get_settings()
    manager = get_job_manager(settings)
    job = manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return TranscriptResponse(
        job_id=job.job_id,
        source_language=job.source_language,
        segments=[
            SegmentOut(
                index=s.index, start=s.start, end=s.end,
                text=s.text, translated_text=s.translated_text,
            )
            for s in job.segments
        ],
    )


@router.get("/jobs/{job_id}/download")
def download_result(job_id: str) -> FileResponse:
    settings = get_settings()
    manager = get_job_manager(settings)
    job = manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.output_path:
        raise HTTPException(status_code=409, detail="Job has no output yet")
    return FileResponse(job.output_path, media_type="video/mp4", filename=job.output_path.split("/")[-1])


@router.websocket("/ws/jobs/{job_id}")
async def job_progress_ws(websocket: WebSocket, job_id: str) -> None:
    await websocket.accept()
    settings = get_settings()
    manager = get_job_manager(settings)
    manager.bind_loop(asyncio.get_running_loop())

    job = manager.get_job(job_id)
    if job is None:
        await websocket.close(code=4404)
        return

    await websocket.send_json({
        "job_id": job.job_id, "status": job.status.value, "stage": job.stage.value,
        "progress": job.progress, "message": job.message,
    })

    queue = manager.subscribe(job_id)
    try:
        while True:
            payload = await queue.get()
            await websocket.send_json(payload)
            if payload["stage"] in ("completed", "failed"):
                break
    except WebSocketDisconnect:
        pass
    finally:
        manager.unsubscribe(job_id, queue)
