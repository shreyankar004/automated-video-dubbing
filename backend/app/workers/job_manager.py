
from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from app.core.config import Settings
from app.core.logging import get_logger, set_job_context
from app.models.job import Job, JobStage
from app.services.pipeline import PipelineError, run_pipeline

logger = get_logger(__name__)


class JobManager:
    def __init__(self, settings: Settings, max_workers: int = 2) -> None:
        self._settings = settings
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def create_job(self, url: str) -> Job:
        job = Job(source_url=url)
        with self._lock:
            self._jobs[job.job_id] = job
        self._executor.submit(self._run, job.job_id)
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def subscribe(self, job_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(job_id, []).append(queue)
        return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        subs = self._subscribers.get(job_id, [])
        if queue in subs:
            subs.remove(queue)

    def _publish(self, job: Job) -> None:
        if not self._loop:
            return
        payload = {
            "job_id": job.job_id,
            "status": job.status.value,
            "stage": job.stage.value,
            "progress": job.progress,
            "message": job.message,
        }
        for queue in list(self._subscribers.get(job.job_id, [])):
            self._loop.call_soon_threadsafe(queue.put_nowait, payload)

    def _run(self, job_id: str) -> None:
        set_job_context(job_id)
        job = self.get_job(job_id)
        if job is None:
            return

        def on_stage(stage: JobStage, progress: int, message: str) -> None:
            job.update(stage=stage, progress=progress, message=message)
            self._publish(job)

        try:
            result = run_pipeline(job.source_url, self._settings, job_id, on_stage=on_stage)
            job.source_title = result.source_title
            job.source_language = result.source_language
            job.source_duration = result.source_duration
            job.segments = result.segments
            job.mark_completed(str(result.output_path))
        except PipelineError as exc:
            logger.error("Job failed: %s", exc)
            job.mark_failed(str(exc))
        except Exception:  # noqa: BLE001 - never leak tracebacks to the client
            logger.exception("Unexpected job failure")
            job.mark_failed("An unexpected error occurred while processing this job.")
        finally:
            self._publish(job)
            set_job_context(None)


_manager: Optional[JobManager] = None


def get_job_manager(settings: Settings) -> JobManager:
    global _manager
    if _manager is None:
        _manager = JobManager(settings)
    return _manager
