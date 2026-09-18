
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000

    whisper_model: str = "small"
    whisper_device: str = "auto"  # auto | cpu | cuda

    translation_provider: str = "web"  # web | local
    translation_model: str = "facebook/nllb-200-distilled-600M"

    tts_provider: str = "edge"
    tts_voice: str = "en-US-AriaNeural"

    # Optional path to a Netscape-format cookies.txt (exported from a logged-in
    # browser) used to get past YouTube's bot checks. Ignored if the file
    # doesn't exist, so it's safe to leave at the default when not needed.
    cookies_file: str = "cookies.txt"

    data_dir: Path = Path("data")
    output_dir: Path = Path("data/output")
    downloads_dir: Path = Path("data/downloads")
    audio_dir: Path = Path("data/audio")
    jobs_dir: Path = Path("data/jobs")

    max_video_duration: int = 10800  # seconds
    max_speech_rate_factor: float = 1.35  # cap on atempo speed-up per segment

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "*"]

    def ensure_directories(self) -> None:
        for path in (self.data_dir, self.output_dir, self.downloads_dir, self.audio_dir, self.jobs_dir):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
