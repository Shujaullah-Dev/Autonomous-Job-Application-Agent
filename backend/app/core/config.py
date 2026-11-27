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

    # Keep job listings fresh. The scheduler runs inside the API process, so
    # the API must stay running for automatic refreshes to happen. A manual
    # refresh from the app or POST /api/v1/jobs/refresh always works.
    job_refresh_enabled: bool = True
    job_refresh_interval_hours: float = 6.0
    job_refresh_on_startup: bool = False
    job_refresh_max_per_source: int = 60
    job_refresh_min_interval_seconds: int = 600
    langchain_explanations_enabled: bool = False
    application_drafts_ai_enabled: bool = False
    
    # Supabase Auth identity verification. Configure SUPABASE_URL, or set the
    # JWT secret/JWKS URL explicitly. No value here belongs in the frontend.
    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    supabase_jwks_url: str = ""
    supabase_jwt_issuer: str = ""
    supabase_jwt_audience: str = "authenticated"

    # Durable LangGraph checkpoints. Without a PostgreSQL URL the workflow
    # graph keeps its in-process memory saver.
    langgraph_checkpoint_url: str = ""

    # Groq
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    resume_ai_enabled: bool = False
    groq_timeout_seconds: float = 30.0
    groq_max_chars: int = 20000
    # Reasoning models spend part of this budget on hidden reasoning before
    # writing the JSON, so the cap must leave room for both.
    groq_max_completion_tokens: int = 8000

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

    @property
    def identity_jwks_url(self) -> str:
        """JWKS endpoint used to verify Supabase access tokens."""

        if self.supabase_jwks_url:
            return self.supabase_jwks_url.rstrip("/")
        if self.supabase_url:
            return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        return ""

    @property
    def identity_issuer(self) -> str:
        """Expected issuer for Supabase access tokens."""

        if self.supabase_jwt_issuer:
            return self.supabase_jwt_issuer.rstrip("/")
        if self.supabase_url:
            return f"{self.supabase_url.rstrip('/')}/auth/v1"
        return ""

    @property
    def identity_configured(self) -> bool:
        """True when access tokens can be verified end to end."""

        return bool(self.supabase_jwt_secret or self.identity_jwks_url)

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()