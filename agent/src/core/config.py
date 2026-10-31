"""Central settings — loads the gitignored repo-root .env.local.

All secrets live in /.env.local (never committed). This module is the single place
that reads them, so the rest of the code imports `settings` and never touches os.environ.
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# agent/src/core/config.py -> parents[3] is the repo root (the dir holding .env.local)
_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILE = _REPO_ROOT / ".env.local"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-6-luna"

    # Tiger Data / TimescaleDB (PostgreSQL connection string)
    tiger_database_url: str = ""

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    # CORS: comma-separated frontend origins allowed to call the API.
    frontend_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    # Admin token (X-API-Key) required by write/agent-trigger endpoints. Empty = those
    # endpoints are disabled (never exposed unauthenticated).
    admin_token: str = ""

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_origins.split(",") if o.strip()]

    @property
    def repo_root(self) -> Path:
        return _REPO_ROOT


settings = Settings()
