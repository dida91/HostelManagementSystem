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
    gemini_text_model: str = Field(default="gemini-3.5-flash", alias="GEMINI_TEXT_MODEL")
    gemini_fast_model: str = Field(default="gemini-3.5-flash-lite", alias="GEMINI_FAST_MODEL")
    gemini_embedding_model: str = Field(
        default="gemini-embedding-001", alias="GEMINI_EMBEDDING_MODEL"
    )
    gemini_embedding_dim: int = Field(default=768, alias="GEMINI_EMBEDDING_DIM")
    # Embeddings are free on the Gemini API free tier. Set false only if this
    # deployment is on a paid key, so cost reporting reflects reality.
    gemini_embedding_free_tier: bool = Field(default=True, alias="GEMINI_EMBEDDING_FREE_TIER")
    gemini_timeout_seconds: float = Field(default=30.0, alias="GEMINI_TIMEOUT_SECONDS")
    gemini_max_retries: int = Field(default=3, alias="GEMINI_MAX_RETRIES")
    gemini_max_tool_iterations: int = Field(default=5, alias="GEMINI_MAX_TOOL_ITERATIONS")

    ai_required: bool = Field(default=True, alias="AI_REQUIRED")
    ai_log_payloads: bool = Field(default=False, alias="AI_LOG_PAYLOADS")

    @field_validator("gemini_embedding_dim")
    @classmethod
    def _valid_dim(cls, v: int) -> int:
        # Gemini embedding models support Matryoshka truncation anywhere in
        # 128..3072; 768, 1536 and 3072 are the recommended values.
        if not 128 <= v <= 3072:
            raise ValueError(
                f"GEMINI_EMBEDDING_DIM={v} is out of range "
                "(supported output dimensionality is 128 to 3072)"
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


class NotificationSettings(BaseSettings):
    """Outbound email and SMS.

    Each channel stays OFF until it is configured. An unconfigured channel is
    simply not used -- in-app notifications still work -- and there is no fake
    sender that would make an unconfigured deployment look like it is mailing
    residents.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    smtp_host: str | None = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str | None = Field(default=None, alias="SMTP_USERNAME")
    smtp_password: SecretStr | None = Field(default=None, alias="SMTP_PASSWORD")
    smtp_security: Literal["starttls", "ssl", "none"] = Field(
        default="starttls", alias="SMTP_SECURITY"
    )
    smtp_timeout_seconds: float = Field(default=15.0, alias="SMTP_TIMEOUT_SECONDS")
    email_from: str = Field(default="Kutumba Hostel <no-reply@kutumba.local>", alias="EMAIL_FROM")

    sms_provider: Literal["none", "sparrow"] = Field(default="none", alias="SMS_PROVIDER")
    sparrow_sms_token: SecretStr | None = Field(default=None, alias="SPARROW_SMS_TOKEN")
    sparrow_sms_from: str | None = Field(default=None, alias="SPARROW_SMS_FROM")
    sparrow_sms_url: str = Field(
        default="https://api.sparrowsms.com/v2/sms/", alias="SPARROW_SMS_URL"
    )

    @property
    def email_enabled(self) -> bool:
        return bool(self.smtp_host and self.smtp_host.strip())

    @property
    def sms_enabled(self) -> bool:
        return (
            self.sms_provider == "sparrow"
            and self.sparrow_sms_token is not None
            and bool(self.sparrow_sms_token.get_secret_value().strip())
            and bool(self.sparrow_sms_from and self.sparrow_sms_from.strip())
        )

    def validate_for_startup(self, app_env: AppEnv) -> None:
        if self.sms_provider == "sparrow" and not self.sms_enabled:
            raise ConfigurationError(
                "SMS_PROVIDER=sparrow, but SPARROW_SMS_TOKEN or SPARROW_SMS_FROM is missing.\n"
                "  Fix: set both in apps/api/.env, or set SMS_PROVIDER=none."
            )
        if app_env == "production" and self.email_enabled and self.smtp_security == "none":
            raise ConfigurationError(
                "SMTP_SECURITY=none is not permitted in production "
                "(credentials and resident data would cross the network unencrypted)."
            )


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

    # Used for links in outbound email; the browser-facing Next.js origin.
    web_base_url: str = Field(default="http://localhost:3000", alias="WEB_BASE_URL")
    # Calendar dates ("today", "due on the 10th") are the hostel's, not the server's.
    hostel_timezone: str = Field(default="Asia/Kathmandu", alias="HOSTEL_TIMEZONE")

    # --- Billing ---
    invoice_due_day: int = Field(default=10, alias="INVOICE_DUE_DAY")
    fee_reminder_days_before_due: int = Field(default=3, alias="FEE_REMINDER_DAYS_BEFORE_DUE")
    auto_generate_monthly_invoices: bool = Field(
        default=True, alias="AUTO_GENERATE_MONTHLY_INVOICES"
    )

    # --- Reports ---
    # A Devanagari TTF so Nepali text prints correctly in PDF exports.
    report_devanagari_font: str = Field(
        default="/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
        alias="REPORT_DEVANAGARI_FONT",
    )

    ai: AISettings = Field(default_factory=AISettings)
    notify: NotificationSettings = Field(default_factory=NotificationSettings)

    @field_validator("invoice_due_day")
    @classmethod
    def _valid_due_day(cls, v: int) -> int:
        # Capped at 28 so every month, including February, has that day.
        if not 1 <= v <= 28:
            raise ValueError("INVOICE_DUE_DAY must be between 1 and 28")
        return v

    @field_validator("hostel_timezone")
    @classmethod
    def _valid_timezone(cls, v: str) -> str:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"HOSTEL_TIMEZONE={v!r} is not a known IANA timezone") from exc
        return v

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
        self.notify.validate_for_startup(self.app_env)

    def __repr__(self) -> str:  # pragma: no cover - defensive, avoids secret leakage
        return f"<Settings app_env={self.app_env} (secrets redacted)>"

    __str__ = __repr__


@lru_cache
def get_settings() -> Settings:
    return Settings()
