from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "whisper_model" in body


def test_create_job_rejects_invalid_url():
    response = client.post("/api/jobs", json={"url": "https://example.com/not-a-video"})
    assert response.status_code == 422


def test_create_job_accepts_valid_url_and_returns_queued(monkeypatch):
    from app.workers.job_manager import JobManager

    
    monkeypatch.setattr(JobManager, "_run", lambda self, job_id: None)

    response = client.post("/api/jobs", json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "queued"
    assert len(body["job_id"]) > 0


def test_get_unknown_job_returns_404():
    response = client.get("/api/jobs/does-not-exist")
    assert response.status_code == 404
