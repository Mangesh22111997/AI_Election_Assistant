"""
backend/config.py
─────────────────
Centralised configuration management using pydantic-settings.
All values are loaded from environment variables / .env file.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings, sourced from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Google / Gemini ───────────────────────────────────────────────────────
    google_api_key: str = Field(..., description="Gemini API key from Google AI Studio")
    gemini_model: str = Field("gemini-1.5-flash-002", description="Gemini model identifier")

    # ── Firebase ──────────────────────────────────────────────────────────────
    firebase_api_key: str = Field(default="", description="Firebase web API key")
    firebase_auth_domain: str = Field(default="", description="Firebase auth domain")
    firebase_project_id: str = Field(default="", description="Firebase / GCP project ID")
    firebase_storage_bucket: str = Field(default="", description="Firebase storage bucket")
    firebase_messaging_sender_id: str = Field(default="", description="Firebase messaging ID")
    firebase_app_id: str = Field(default="", description="Firebase app ID")
    firebase_admin_sdk_path: str = Field(
        default="firebase-adminsdk.json",
        description="Path to the Firebase admin SDK service-account JSON",
    )
    firebase_database_url: str = Field(default="", description="Firebase Realtime Database URL")

    # ── Google Custom Search ──────────────────────────────────────────────────
    google_cse_id: str = Field(default="", description="Google Custom Search Engine ID")
    google_cse_api_key: str = Field(default="", description="Google CSE API key")

    # ── Application ───────────────────────────────────────────────────────────
    app_env: Literal["development", "production"] = Field(
        default="development", description="Runtime environment"
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="Logging verbosity"
    )
    secret_key: str = Field(
        default="change_me_to_a_long_random_string",
        description="Secret key for JWT signing",
    )

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    rate_limit_requests: int = Field(default=60, ge=1, description="Max requests per period")
    rate_limit_period: int = Field(default=60, ge=1, description="Rate-limit window in seconds")

    # ── Network ───────────────────────────────────────────────────────────────
    backend_url: str = Field(
        default="http://localhost:8000",
        description="Backend URL for internal self-referencing (health pings)"
    )
    frontend_url: str = Field(
        default="http://localhost:8501",
        description="Frontend origin URL for CORS whitelist in production"
    )
    frontend_port: int = Field(default=8501)
    backend_port: int = Field(default=8000)

    # ── Gemini Inference ──────────────────────────────────────────────────────
    gemini_temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Low temperature for high factual accuracy",
    )
    gemini_max_output_tokens: int = Field(default=1024, ge=128)
    max_clarification_attempts: int = Field(
        default=3,
        ge=1,
        description="Max attempts before escalating to 'Contact Election Office'",
    )

    # ── RAG ───────────────────────────────────────────────────────────────────
    vector_store_path: str = Field(default="data/vector_store")
    similarity_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    max_retrieval_contexts: int = Field(default=5, ge=1)

    @field_validator("google_api_key")
    @classmethod
    def _require_api_key(cls, v: str) -> str:
        if not v or v == "your_gemini_api_key_here":
            raise ValueError(
                "GOOGLE_API_KEY must be set to a valid Gemini API key. "
                "Get one at https://aistudio.google.com/apikey"
            )
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def firebase_config(self) -> dict:
        """Return the Firebase web SDK configuration dict."""
        return {
            "apiKey": self.firebase_api_key,
            "authDomain": self.firebase_auth_domain,
            "projectId": self.firebase_project_id,
            "storageBucket": self.firebase_storage_bucket,
            "messagingSenderId": self.firebase_messaging_sender_id,
            "appId": self.firebase_app_id,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
