import time

from app.core.config import Settings
from app.models.job import JobStatus
from app.workers import job_manager as job_manager_module


def _settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        data_dir=tmp_path,
        output_dir=tmp_path / "output",
        downloads_dir=tmp_path / "downloads",
        audio_dir=tmp_path / "audio",
        jobs_dir=tmp_path / "jobs",
    )


def test_create_job_starts_as_queued_or_processing(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    settings.ensure_directories()

    def fake_pipeline(url, settings_, job_id, on_stage=None):
        time.sleep(0.05)
        raise job_manager_module.PipelineError("simulated failure")

    monkeypatch.setattr(job_manager_module, "run_pipeline", fake_pipeline)

    manager = job_manager_module.JobManager(settings)
    job = manager.create_job("https://www.youtube.com/watch?v=abc12345678")

    assert job.status in (JobStatus.QUEUED, JobStatus.PROCESSING)
    assert job.job_id


    for _ in range(50):
        if manager.get_job(job.job_id).status == JobStatus.FAILED:
            break
        time.sleep(0.02)

    final = manager.get_job(job.job_id)
    assert final.status == JobStatus.FAILED
    assert "simulated failure" in final.error


def test_get_job_returns_none_for_unknown_id(tmp_path):
    settings = _settings(tmp_path)
    settings.ensure_directories()
    manager = job_manager_module.JobManager(settings)
    assert manager.get_job("does-not-exist") is None
