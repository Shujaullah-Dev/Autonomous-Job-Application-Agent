
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# Resolve .env from the project root, not the
# directory where Python was launched.
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "AI Job Agent"
    app_env: str = "development"
    debug: bool = False
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    database_url: str

    # Groq AI
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    resume_ai_enabled: bool = True
    groq_timeout_seconds: float = 30.0
    groq_max_chars: int = 20000

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
