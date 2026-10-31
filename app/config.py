"""Central application configuration (the only place environment variables are read)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()  # load .env file if present, so env vars can be overridden in the shell
import os

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Settings loaded from environment variables and an optional .env file."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=False,
        extra="ignore",
    )

    # LLM
    openrouter_api_key: str = os.environ.get("OPENROUTER_API_KEY", "")
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_site_url: str = ""   # optional, shown on OpenRouter rankings
    openrouter_app_name: str = "Student Feedback Agent"
    llm_model: str = os.environ.get("LLM_MODEL", "recursive/flint-v1.0:free")
    llm_temperature: float = 0.2
    llm_timeout_seconds: int = 60

    # Tavily
    tavily_api_key: str = os.environ.get("TAVILY_API_KEY", "")
    tavily_timeout_seconds: int = 20
    max_resource_subjects: int = 3
    max_results_per_search: int = 4
    mastery_min_questions: int = 8
    mastery_min_sessions: int = 2

    # Storage
    database_url: str = "sqlite:///./student_feedback.db"
    upload_directory: Path = Path("storage/uploads")
    report_directory: Path = Path("storage/reports")
    chart_directory: Path = Path("storage/charts")
    max_upload_mb: int = 10
    keep_uploaded_files: bool = False

    # Logging / CORS
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:8501,http://127.0.0.1:8501"

    # Analysis defaults (every threshold is also returned alongside results so it can be explained)
    weak_threshold: float = 50.0
    strong_threshold: float = 75.0
    relative_gap: float = 10.0
    decline_points: float = 5.0
    inconsistency_std: float = 10.0
    target_gap: float = 10.0

    @field_validator(
        "llm_model", "openrouter_base_url", "database_url", "upload_directory", "report_directory", "chart_directory", mode="before"
    )
    @classmethod
    def _empty_means_default(cls, value, info):
        """Treat `KEY=` (empty) in .env as 'use the default'."""
        if value is None or (isinstance(value, str) and not value.strip()):
            return cls.model_fields[info.field_name].default
        return value

    @property
    def sqlalchemy_url(self) -> str:
        """Database URL with relative SQLite paths anchored at the project root."""
        prefix = "sqlite:///./"
        if self.database_url.startswith(prefix):
            return "sqlite:///" + (BASE_DIR / self.database_url[len(prefix):]).as_posix()
        return self.database_url

    def resolve_dir(self, path: Path) -> Path:
        """Return an absolute directory path, creating the directory if needed."""
        resolved = path if path.is_absolute() else BASE_DIR / path
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    @property
    def upload_path(self) -> Path:
        return self.resolve_dir(self.upload_directory)

    @property
    def report_path(self) -> Path:
        return self.resolve_dir(self.report_directory)

    @property
    def chart_path(self) -> Path:
        return self.resolve_dir(self.chart_directory)

    @property
    def llm_configured(self) -> bool:
        return bool(self.openrouter_api_key.strip())

    @property
    def tavily_configured(self) -> bool:
        return bool(self.tavily_api_key.strip())

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance (call `get_settings.cache_clear()` in tests after changing env)."""
    return Settings()
