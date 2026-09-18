"""Centralised, environment-driven configuration.

Model names and credentials are NEVER hardcoded in business logic; everything
resolves from here. Validation happens once at application startup.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["local", "test", "staging", "production"]


class ConfigurationError(RuntimeError):
    """Raised when configuration is invalid. Message is operator-facing only."""


class AISettings(BaseSettings):
    """Gemini / AI provider configuration."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    gemini_api_key: SecretStr | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_text_model: str = Field(default="gemini-2.5-pro", alias="GEMINI_TEXT_MODEL")
    gemini_fast_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_FAST_MODEL")
    gemini_embedding_model: str = Field(
        default="gemini-embedding-001", alias="GEMINI_EMBEDDING_MODEL"
    )
    gemini_embedding_dim: int = Field(default=768, alias="GEMINI_EMBEDDING_DIM")
    gemini_timeout_seconds: float = Field(default=30.0, alias="GEMINI_TIMEOUT_SECONDS")
    gemini_max_retries: int = Field(default=3, alias="GEMINI_MAX_RETRIES")
    gemini_max_tool_iterations: int = Field(default=5, alias="GEMINI_MAX_TOOL_ITERATIONS")

    ai_required: bool = Field(default=True, alias="AI_REQUIRED")
    ai_log_payloads: bool = Field(default=False, alias="AI_LOG_PAYLOADS")

    @field_validator("gemini_embedding_dim")
    @classmethod
    def _valid_dim(cls, v: int) -> int:
        # gemini-embedding-001 supports Matryoshka truncation to these sizes.
        if v not in (128, 256, 512, 768, 1536, 3072):
            raise ValueError(
                f"GEMINI_EMBEDDING_DIM={v} is not a supported output dimensionality "
                "(expected one of 128, 256, 512, 768, 1536, 3072)"
            )
        return v

    @field_validator("gemini_max_retries")
    @classmethod
    def _bounded_retries(cls, v: int) -> int:
        if not 0 <= v <= 5:
            raise ValueError("GEMINI_MAX_RETRIES must be between 0 and 5 (no unbounded retries)")
        return v

    def validate_for_startup(self, app_env: AppEnv) -> None:
        """Fail clearly when AI is required but unconfigured.

        We deliberately do NOT fall back to a stub implementation: a silent fake
        would make an unconfigured deployment look healthy.
        """
        if not self.ai_required:
            return
        if self.gemini_api_key is None or not self.gemini_api_key.get_secret_value().strip():
            raise ConfigurationError(
                "GEMINI_API_KEY is not set, but AI_REQUIRED=true.\n"
                "  Fix: add GEMINI_API_KEY to apps/api/.env (copy apps/api/.env.example).\n"
                "  Or:  set AI_REQUIRED=false to boot with AI endpoints disabled.\n"
                "  Note: .env is gitignored and must never be committed."
            )
        if app_env == "production" and self.ai_log_payloads:
            raise ConfigurationError(
                "AI_LOG_PAYLOADS=true is not permitted in production "
                "(it would write prompt and response bodies to logs)."
            )

    @property
    def is_configured(self) -> bool:
        return bool(self.gemini_api_key and self.gemini_api_key.get_secret_value().strip())


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: AppEnv = Field(default="local", alias="APP_ENV")
    app_debug: bool = Field(default=False, alias="APP_DEBUG")
    secret_key: SecretStr = Field(default=SecretStr("dev-only-change-me"), alias="SECRET_KEY")
    api_base_url: str = Field(default="http://localhost:8000", alias="API_BASE_URL")
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    database_url: str = Field(
        default="postgresql+asyncpg://hostel:hostel@localhost:5434/hostel",
        alias="DATABASE_URL",
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg://hostel:hostel@localhost:5434/hostel",
        alias="DATABASE_URL_SYNC",
    )

    redis_url: str = Field(default="redis://localhost:6380/0", alias="REDIS_URL")
    celery_broker_url: str = Field(default="redis://localhost:6380/1", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(
        default="redis://localhost:6380/2", alias="CELERY_RESULT_BACKEND"
    )

    access_token_ttl_minutes: int = Field(default=15, alias="ACCESS_TOKEN_TTL_MINUTES")
    refresh_token_ttl_days: int = Field(default=7, alias="REFRESH_TOKEN_TTL_DAYS")

    storage_dir: str = Field(default="./storage", alias="STORAGE_DIR")
    max_upload_bytes: int = Field(default=20 * 1024 * 1024, alias="MAX_UPLOAD_BYTES")

    ai: AISettings = Field(default_factory=AISettings)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def validate_for_startup(self) -> None:
        if self.app_env == "production":
            if self.secret_key.get_secret_value() in {"dev-only-change-me", "change-me"}:
                raise ConfigurationError("SECRET_KEY must be set to a strong value in production.")
            if self.app_debug:
                raise ConfigurationError("APP_DEBUG must be false in production.")
        self.ai.validate_for_startup(self.app_env)

    def __repr__(self) -> str:  # pragma: no cover - defensive, avoids secret leakage
        return f"<Settings app_env={self.app_env} (secrets redacted)>"

    __str__ = __repr__


@lru_cache
def get_settings() -> Settings:
    return Settings()
