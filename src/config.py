"""Centralised configuration loaded from environment / .env."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parent.parent
CONTEXT_DIR = ROOT / "context"
DATA_DIR = ROOT / "data"
WEB_DIR = ROOT / "web"

PostingMode = Literal["dry_run", "manual_review", "auto"]


class Settings(BaseSettings):
    """Runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5-20250929"

    # LinkedIn
    linkedin_email: str = ""
    linkedin_password: str = ""

    # Server
    host: str = "127.0.0.1"
    port: int = 8000

    # Storage
    database_url: str = f"sqlite:///{DATA_DIR / 'posts.db'}"

    # Replicate (image generation)
    replicate_api_token: str = ""
    replicate_model: str = "black-forest-labs/flux-schnell"

    # Reddit (optional, for higher rate limits on trend scout)
    reddit_client_id: str = ""
    reddit_client_secret: str = ""

    # Behaviour
    posting_mode: PostingMode = "manual_review"
    schedule_cron: str = "0 9 * * 1-5"
    trend_refresh_cron: str = "0 7 * * *"  # daily at 07:00 UTC


settings = Settings()


def ensure_dirs() -> None:
    """Make sure data and storage folders exist before use."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "drafts").mkdir(exist_ok=True)
    (DATA_DIR / "published").mkdir(exist_ok=True)
    (DATA_DIR / "screenshots").mkdir(exist_ok=True)
    (DATA_DIR / "images").mkdir(exist_ok=True)
