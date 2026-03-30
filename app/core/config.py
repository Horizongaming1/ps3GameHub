from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ps3cache-api"
    app_env: str = "production"
    api_host: str = "0.0.0.0"
    api_port: int = 8080

    database_url: str = "sqlite:////data/ps3cache.db"
    library_root: str = "/library"

    log_level: str = "INFO"
    log_dir: str = "/logs"
    log_file_name: str = "app.log"

    scan_on_startup: bool = True
    scan_recursive: bool = True

    worker_poll_interval_sec: float = 2.0
    worker_copy_chunk_size: int = 1024 * 1024
    worker_max_retries: int = 1

    ftp_timeout_sec: float = 20.0
    webman_timeout_sec: float = 4.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def log_file_path(self) -> Path:
        return Path(self.log_dir) / self.log_file_name


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
