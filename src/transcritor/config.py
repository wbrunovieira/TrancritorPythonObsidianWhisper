from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    whisper_model: str = "base"
    data_dir: Path = Path.home() / ".transcritor"
    redis_url: str = "redis://localhost:6379/0"
    log_level: str = "INFO"
    api_key: str = ""
    result_ttl_hours: int = 24
    youtube_cookies_file: Path = Path("/config/youtube_cookies.txt")

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"

    @property
    def video_dir(self) -> Path:
        return self.data_dir / "video"

    @property
    def transcripts_dir(self) -> Path:
        return self.data_dir / "transcripts"


@lru_cache
def get_settings() -> Settings:
    return Settings()
