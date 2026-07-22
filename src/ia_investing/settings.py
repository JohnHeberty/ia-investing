from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


class DatabaseSettings(BaseModel):
    url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/stock_intelligence"
    pool_size: int = Field(default=10, ge=1)
    max_overflow: int = Field(default=20, ge=0)


class StorageSettings(BaseModel):
    endpoint: str = "http://localhost:9000"
    access_key: SecretStr = SecretStr("")
    secret_key: SecretStr = SecretStr("")
    bucket: str = "raw-documents"


class TemporalSettings(BaseModel):
    address: str = "localhost:7233"
    namespace: str = "default"
    task_queue: str = "stock-intelligence"


class AIGatewaySettings(BaseModel):
    provider: Literal["openai", "anthropic"] = "openai"
    api_key: SecretStr = SecretStr("")
    model: str = "gpt-4o"
    timeout: float = Field(default=120.0, ge=1.0)
    max_retries: int = Field(default=3, ge=0, le=10)
    base_url: str | None = None
    rpm: int = Field(default=60, ge=1)
    tpm: int = Field(default=100_000, ge=1)

    @model_validator(mode="after")
    def validate_config(self) -> AIGatewaySettings:
        raw = self.api_key.get_secret_value()
        if raw and len(raw) < 8:
            raise ValueError("AI gateway API key is too short")
        if self.provider == "anthropic" and self.model and "claude" not in self.model:
            raise ValueError("Anthropic models should contain 'claude'")
        return self


class AISettings(BaseModel):
    provider: Literal["mock", "openai", "gateway"] = "mock"
    openai_api_key: SecretStr = SecretStr("")
    openai_base_url: str = "https://api.openai.com/v1"
    litellm_gateway_url: str | None = None
    gateway: AIGatewaySettings = Field(default_factory=AIGatewaySettings)


class TelemetrySettings(BaseModel):
    otlp_endpoint: str | None = None
    enabled: bool = False
    mlflow_tracking_uri: str | None = None


class SecuritySettings(BaseModel):
    oidc_enabled: bool = False
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_jwks_url: str | None = None
    ssrf_allowed_internal_hosts: list[str] = Field(
        default_factory=lambda: ["postgres", "minio", "temporal", "localhost", "127.0.0.1"],
        description="Hostnames allowed for internal SSRF requests",
    )
    content_security_policy: str = Field(
        default=_DEFAULT_CSP,
        description="Content-Security-Policy header value",
    )
    oidc_authorization_url: str | None = None
    oidc_token_url: str | None = None
    oidc_end_session_url: str | None = None
    oidc_redirect_uri: str = "http://localhost:3000/api/auth/callback"
    oidc_scope: str = "openid profile email offline_access"
    session_secret_key: str = ""
    csrf_secret_key: str = ""


class SchedulerSettings(BaseModel):
    cvm_cnpj: str | None = None
    cvm_issuer_id: str | None = None
    cvm_year: int = Field(default=2025, ge=2000, le=2100)
    cvm_statement_type: str = "DRE_con"
    paper_portfolio_id: str | None = None
    paper_organization_id: str | None = None
    paper_portfolio_version_id: str | None = None
    paper_rebalance_input_sha256: str | None = None


class WorkerSettings(BaseModel):
    capability: Literal[
        "data-ingestion",
        "document-processing",
        "research-agents",
        "portfolio-risk",
        "notifications",
    ] = "research-agents"
    activity_threads: int = Field(default=8, ge=1, le=64)


class ApplicationSettings(BaseModel):
    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "DEBUG"


class Settings(BaseSettings):
    """Canonical application configuration loaded from environment and root .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        env_nested_max_split=1,
        extra="ignore",
    )

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    temporal: TemporalSettings = Field(default_factory=TemporalSettings)
    ai: AISettings = Field(default_factory=AISettings)
    telemetry: TelemetrySettings = Field(default_factory=TelemetrySettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)
    worker: WorkerSettings = Field(default_factory=WorkerSettings)
    application: ApplicationSettings = Field(default_factory=ApplicationSettings)

    @model_validator(mode="after")
    def validate_production(self) -> Settings:
        if self.application.environment != "production":
            return self

        required = {
            "STORAGE__ACCESS_KEY": self.storage.access_key.get_secret_value(),
            "STORAGE__SECRET_KEY": self.storage.secret_key.get_secret_value(),
            "SECURITY__OIDC_ISSUER": self.security.oidc_issuer,
            "SECURITY__OIDC_AUDIENCE": self.security.oidc_audience,
            "SECURITY__OIDC_JWKS_URL": self.security.oidc_jwks_url,
        }
        missing = [name for name, value in required.items() if not value]
        if self.ai.provider == "mock":
            missing.append("AI__PROVIDER (mock is forbidden in production)")
        if self.ai.provider == "openai" and not self.ai.openai_api_key.get_secret_value():
            missing.append("AI__OPENAI_API_KEY")
        if "postgres:postgres@localhost" in self.database.url:
            missing.append("DATABASE__URL (must not use development credentials)")
        if missing:
            raise ValueError("production configuration is missing required values: " + ", ".join(missing))
        return self

    # Transitional compatibility accessors. New code must use grouped settings.
    @property
    def database_url(self) -> str:
        return self.database.url

    @property
    def db_pool_size(self) -> int:
        return self.database.pool_size

    @property
    def db_max_overflow(self) -> int:
        return self.database.max_overflow

    @property
    def storage_endpoint(self) -> str:
        return self.storage.endpoint

    @property
    def temporal_address(self) -> str:
        return self.temporal.address

    @property
    def temporal_namespace(self) -> str:
        return self.temporal.namespace

    @property
    def temporal_task_queue(self) -> str:
        return self.temporal.task_queue

    @property
    def app_env(self) -> str:
        return self.application.environment


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
