"""Application configuration.

Every setting can be overridden through environment variables or a `.env`
file placed at the repository root (see `.env.example`).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ----- Application ------------------------------------------------------
    APP_NAME: str = "RetailVoice AI"
    APP_ENV: Literal["development", "staging", "production", "test"] = "development"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True

    # ----- Security ---------------------------------------------------------
    SECRET_KEY: str = "CHANGE-ME-in-production-a-long-random-string"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 14
    JWT_ALGORITHM: str = "HS256"
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"

    # ----- Database ---------------------------------------------------------
    # SQLite keeps the project runnable with zero infrastructure.
    # For Postgres: postgresql+asyncpg://user:pass@localhost:5432/retailvoice
    DATABASE_URL: str = "sqlite+aiosqlite:///./retailvoice.db"
    DB_ECHO: bool = False

    # ----- LLM provider -----------------------------------------------------
    # "anthropic" -> real Claude calls; "mock" -> deterministic offline agent.
    # "auto" picks anthropic when ANTHROPIC_API_KEY is present, else mock.
    LLM_PROVIDER: Literal["auto", "anthropic", "mock"] = "auto"
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL: str = "claude-sonnet-5"
    LLM_FALLBACK_MODEL: str = "claude-haiku-4-5-20251001"
    LLM_MAX_TOKENS: int = 1200
    LLM_TEMPERATURE: float = 0.3
    AGENT_MAX_TOOL_ITERATIONS: int = 6

    # ----- Speech-to-text ---------------------------------------------------
    # "browser" -> the client does STT with the Web Speech API (zero config)
    # "whisper" -> local faster-whisper, "deepgram" -> hosted API, "mock" -> stub
    STT_PROVIDER: Literal["browser", "whisper", "deepgram", "mock"] = "browser"
    WHISPER_MODEL_SIZE: str = "base"
    WHISPER_DEVICE: str = "cpu"
    DEEPGRAM_API_KEY: str = ""

    # ----- Text-to-speech ---------------------------------------------------
    # "browser" -> SpeechSynthesis in the client, "elevenlabs" -> hosted,
    # "pyttsx3" -> offline OS voices, "mock" -> silent wav
    TTS_PROVIDER: Literal["browser", "elevenlabs", "pyttsx3", "mock"] = "browser"
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = "21m00Tcm4TlvDq8ikWAM"
    TTS_SAMPLE_RATE: int = 22050

    # ----- Retrieval (RAG) --------------------------------------------------
    # "hashing" is a dependency-free deterministic embedder good enough for a
    # few thousand chunks; "sentence-transformers" gives better recall.
    EMBEDDING_PROVIDER: Literal["hashing", "sentence-transformers"] = "hashing"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIM: int = 384
    RAG_TOP_K: int = 4
    RAG_MIN_SCORE: float = 0.12
    RAG_CHUNK_SIZE: int = 700
    RAG_CHUNK_OVERLAP: int = 120

    # ----- Agent policy -----------------------------------------------------
    ESCALATION_SENTIMENT_THRESHOLD: float = -0.55
    ESCALATION_MAX_TURNS_WITHOUT_RESOLUTION: int = 8
    ESCALATION_REFUND_AMOUNT_LIMIT: float = 5000.0
    ENABLE_PII_REDACTION: bool = True
    # DEMO ONLY: lets a signed-out visitor look up an order by its number.
    # Turn this off in production - order data must be behind authentication.
    ALLOW_ANONYMOUS_ORDER_LOOKUP: bool = True
    GOODWILL_COUPON_MAX_VALUE: float = 500.0

    # ----- Voice session ----------------------------------------------------
    VOICE_MAX_SESSION_SECONDS: int = 900
    VOICE_SILENCE_TIMEOUT_MS: int = 1500

    # ----- Seed / demo ------------------------------------------------------
    SEED_ON_STARTUP: bool = True
    DEMO_ADMIN_EMAIL: str = "admin@retailvoice.ai"
    DEMO_ADMIN_PASSWORD: str = "Admin@123"

    # ----- Derived ----------------------------------------------------------
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def resolved_llm_provider(self) -> str:
        if self.LLM_PROVIDER != "auto":
            return self.LLM_PROVIDER
        return "anthropic" if self.ANTHROPIC_API_KEY.strip() else "mock"

    @field_validator("CORS_ORIGINS")
    @classmethod
    def _strip_cors(cls, v: str) -> str:
        return v.strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
