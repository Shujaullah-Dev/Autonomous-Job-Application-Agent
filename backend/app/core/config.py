from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]

class Settings(BaseSettings):
    app_name: str = "AI Job Agent"
    app_env: str = "development"
    debug: bool = False
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    frontend_url: str = "http://localhost:3000"

    database_url: str
    dev_job_write_key: str
    job_source_timeout_seconds: float = 20.0
    langchain_explanations_enabled: bool = False
    application_drafts_ai_enabled: bool = False
    
    # Groq
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    resume_ai_enabled: bool = False
    groq_timeout_seconds: float = 30.0
    groq_max_chars: int = 20000

    @property
    def cors_origins(self) -> list[str]:
        """Origins allowed to call this API from a browser."""

        origins = [
            self.frontend_url.rstrip("/"),
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
        seen: list[str] = []
        for origin in origins:
            if origin and origin not in seen:
                seen.append(origin)
        return seen

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()