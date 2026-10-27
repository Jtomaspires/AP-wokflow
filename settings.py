"""Central application configuration loaded from environment variables."""

from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings and feature flags for the P2P workflow."""

    # Infrastructure
    DATABASE_URL: str = "postgresql+psycopg2://lab:lab_dev@localhost:5434/lab"
    REDIS_URL: str = "redis://localhost:6380/0"

    # Workflow
    CONFIDENCE_THRESHOLD: float = 0.7
    NEAR_DUE_DAYS: int = 7
    VAT_RATE: float = 0.23
    MATCH_VALUE_TOLERANCE_PCT: float = 0.02
    MATCH_VALUE_TOLERANCE_ABS: float = 1.00
    MATCH_FUZZY_CUTOFF: float = 0.85
    RESOLUTION_RETRY_ENABLED: bool = False
    RESOLUTION_RETRY_MIN_CONFIDENCE: float = 0.85
    RESOLUTION_RETRY_MAX: int = 1
    RESOLUTION_RETRY_TOLERANCE_MULTIPLIER: float = 4.0
    RESOLUTION_RETRY_FUZZY_FLOOR: float = 0.75
    WORKFLOW_SUCCESS_THRESHOLD: float = 0.80
    EVAL_LIVE_LLM: bool = False
    THREAD_MAX_HISTORY_CHARS: int = 2000
    HITL_DEFAULT_DEADLINE_H: int = 24

    # Routing
    DEFAULT_OPERATOR_ID: str = "op_joao"
    ROUTING_NO_RULE_BEHAVIOUR: str = "default"  # "default" | "hitl"

    # Auth
    SESSION_COOKIE_NAME: str = "p2p_session"
    SESSION_TTL_HOURS: int = 12
    COOKIE_SECURE: bool = False
    CORS_ORIGINS: str = "http://localhost:5173"

    # Mailboxes
    INVOICING_EMAIL: str = "invoicing@company.com"
    PAYMENTS_EMAIL: str = "payments@company.com"

    # LLM
    LLM_PRIMARY_MODEL: str = "gpt-4o-mini"
    LLM_PRIMARY_API_KEY: str | None = None
    LLM_PRIMARY_BASE_URL: str | None = None
    LLM_FALLBACK_MODEL: str | None = None
    LLM_FALLBACK_API_KEY: str | None = None
    LLM_FALLBACK_BASE_URL: str | None = None
    LLM_TIMEOUT_S: int = 15
    LLM_RETRY_BACKOFF_S: int = 2

    # Feature flags (safe development defaults)
    NYLAS_SEND_ENABLED: bool = False
    NYLAS_API_KEY: str | None = None
    NYLAS_API_URI: str = "https://api.us.nylas.com"
    NYLAS_GRANT_ID: str | None = None
    NYLAS_WEBHOOK_SECRET: str | None = None
    SPF_DKIM_ENABLED: bool = False
    SECURITY_CHECK_ENABLED: bool = True
    SENDER_DOMAIN_WHITELIST: str = (
        "acme-supplies.com,group-subsidiary.com,p2p-branch.com,company.com,vendor.com,gmail.com"
    )
    TRIAGE_DISCARD_MIN_CONFIDENCE: float = 0.8
    INTENT_MIN_CONFIDENCE: float = 0.5

    @field_validator(
        "LLM_PRIMARY_API_KEY",
        "LLM_PRIMARY_BASE_URL",
        "LLM_FALLBACK_MODEL",
        "LLM_FALLBACK_API_KEY",
        "LLM_FALLBACK_BASE_URL",
        "NYLAS_API_KEY",
        "NYLAS_GRANT_ID",
        "NYLAS_WEBHOOK_SECRET",
        mode="before",
    )
    @classmethod
    def empty_or_placeholder_llm_setting_is_none(cls, value: Any) -> Any:
        """Ignore empty values and documentation placeholders from .env files."""
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped or (stripped.startswith("<") and stripped.endswith(">")):
            return None
        return stripped

    @field_validator("NYLAS_API_URI", mode="before")
    @classmethod
    def blank_nylas_api_uri_is_us_default(cls, value: Any) -> Any:
        """A blank env line must not replace the US Nylas host."""
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped or (stripped.startswith("<") and stripped.endswith(">")):
            return "https://api.us.nylas.com"
        return stripped

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
