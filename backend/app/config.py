from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("CIVITAS_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CIVITAS_", env_file=".env", extra="ignore")

    app_name: str = "CIVITAS"
    environment: Literal["development", "production", "test"] = "development"
    database_url: str = f"sqlite:///{(DATA_DIR / 'civitas.db').as_posix()}"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    api_key: str | None = None
    rate_limit_per_minute: int = 240

    # Optional LLM. The simulation is fully functional without it.
    llm_enabled: bool = False
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 12.0
    llm_max_calls_per_minute: int = 6

    snapshot_interval_days: int = 25
    autosave_interval_days: int = 25
    max_agents_per_run: int = 300
    max_runs_ticking: int = 8

    @field_validator("database_url")
    @classmethod
    def normalize_sqlite(cls, v: str) -> str:
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+psycopg://", 1)
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+psycopg://", 1)
        return v

    @property
    def cors_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def llm_active(self) -> bool:
        return bool(self.llm_enabled and self.llm_api_key)


settings = Settings()
