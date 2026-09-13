"""
CommitmentOS — FastAPI configuration.
All settings read from environment / .env file. No hardcoded values.
"""
from pathlib import Path
from typing import Any
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_root_dir = Path(__file__).resolve().parent.parent.parent
_env_files = [
    str(_root_dir / ".env"),
    str(_root_dir / "apps" / "api" / ".env"),
    ".env",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_files,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://commitmentos:commitmentos@localhost:5432/commitmentos"

    # ── LLM ──────────────────────────────────────────────────────────────────
    llm_provider: str = "groq"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    openai_api_key: str = ""
    openai_base_url: str | None = None
    openai_model: str = "nex-agi/nex-n2.5-mini:free"

    # ── Supermemory ───────────────────────────────────────────────────────────
    supermemory_api_key: str = ""
    supermemory_container_tag: str = "commitment-os"

    # ── Slack ───────────────────────────────────────────────────────────────────────
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    slack_default_channel: str = ""  # Fallback channel ID for reminders/nudges (e.g. C0C1G30AX54)

    # ── Linear ────────────────────────────────────────────────────────────────
    linear_api_key: str = ""

    # ── Gmail ─────────────────────────────────────────────────────────────────
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_refresh_token: str = ""

    # ── App ───────────────────────────────────────────────────────────────────
    environment: str = "development"
    log_level: str = "INFO"
    cors_origins: list[str] | str = ["http://localhost:3000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    import json
                    return json.loads(v)
                except Exception:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    def model_post_init(self, __context: Any) -> None:
        if self.openai_api_key.startswith("sk-or-v1-") and not self.openai_base_url:
            self.openai_base_url = "https://openrouter.ai/api/v1"
        if self.openai_model in ("nvidia/nemotron-3-ultra", "nemotron-3-ultra", "nvidia/nemotron-3-ultra-550b-a55b"):
            self.openai_model = "nvidia/nemotron-3-ultra-550b-a55b:free"




settings = Settings()
