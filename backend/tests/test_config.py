import os

from app.core.config import Settings


def test_default_settings_load():
    settings = Settings(_env_file=None)
    assert settings.whisper_model == "small"
    assert settings.tts_provider == "edge"
    assert settings.translation_provider == "web"


def test_settings_read_environment_overrides(monkeypatch):
    monkeypatch.setenv("WHISPER_MODEL", "medium")
    monkeypatch.setenv("TTS_VOICE", "en-GB-SoniaNeural")
    settings = Settings(_env_file=None)
    assert settings.whisper_model == "medium"
    assert settings.tts_voice == "en-GB-SoniaNeural"


def test_ensure_directories_creates_paths(tmp_path):
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "data" / "output",
        downloads_dir=tmp_path / "data" / "downloads",
        audio_dir=tmp_path / "data" / "audio",
        jobs_dir=tmp_path / "data" / "jobs",
    )
    settings.ensure_directories()
    assert settings.output_dir.exists()
    assert settings.jobs_dir.exists()
