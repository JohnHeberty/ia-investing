from __future__ import annotations

import warnings
from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/stock_intelligence"

    # Storage (S3 / MinIO)
    storage_endpoint: str = "http://localhost:9000"
    storage_access_key: str = ""
    storage_secret_key: str = ""
    storage_bucket: str = "raw-documents"

    # OpenAI API (Agents SDK)
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    # LiteLLM Gateway (optional, for multi-provider routing)
    litellm_gateway_url: str | None = None

    # Temporal (orchestration)
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "stock-intelligence"

    # Observability
    otlp_endpoint: str | None = None
    enable_otel: bool = False

    # MLflow
    mlflow_tracking_uri: str | None = None

    # Application
    app_env: str = "development"
    log_level: str = "DEBUG"

    # Connection pool
    db_pool_size: int = 10
    db_max_overflow: int = 20

    @model_validator(mode="after")
    def _warn_missing_creds(self) -> Settings:
        if self.app_env == "production":
            if not self.storage_access_key:
                warnings.warn("STORAGE_ACCESS_KEY not set — S3 operations will fail", stacklevel=1)
            if not self.storage_secret_key:
                warnings.warn("STORAGE_SECRET_KEY not set — S3 operations will fail", stacklevel=1)
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
