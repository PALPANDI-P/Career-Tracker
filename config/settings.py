"""
Career Tracker — Application Settings

Loads configuration from .env file and provides typed access to all
settings across the pipeline: API keys, thresholds, scheduling, etc.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root is two levels up from config/settings.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """
    Central configuration for the career tracker pipeline.

    Values are loaded from (in priority order):
    1. Environment variables
    2. .env file in project root
    3. Defaults defined here
    """

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        env_prefix="CT_",
        case_sensitive=False,
        extra="ignore",
    )

    # --- LLM Provider ---
    llm_provider: str = Field(
        default="anthropic",
        description="LLM provider: 'anthropic' or 'openai'",
    )
    anthropic_api_key: Optional[str] = Field(
        default=None,
        description="Anthropic API key for Claude calls",
    )
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key (alternative provider)",
    )
    llm_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Model name for LLM calls",
    )
    llm_max_tokens: int = Field(
        default=300,
        ge=50,
        le=2000,
        description="Max tokens per LLM response",
    )

    # --- Telegram ---
    telegram_bot_token: Optional[str] = Field(
        default=None,
        description="Telegram Bot API token",
    )
    telegram_chat_id: Optional[str] = Field(
        default=None,
        description="Telegram chat/channel ID for notifications",
    )

    # --- Matching ---
    match_threshold_high: float = Field(
        default=0.80,
        ge=0.0,
        le=1.0,
        description="Score above this = automatic match (no LLM needed)",
    )
    match_threshold_low: float = Field(
        default=0.55,
        ge=0.0,
        le=1.0,
        description="Score below this = automatic reject (no LLM needed)",
    )
    # Scores between low and high are 'borderline' → routed to LLM judge (Phase 7)

    # --- Seniority Filter ---
    target_seniority_levels: list[str] = Field(
        default=["entry", "junior", "mid"],
        description="Seniority levels to include (lowercase)",
    )

    # --- Scheduling ---
    schedule_interval_hours: int = Field(
        default=6,
        ge=1,
        description="Hours between automated pipeline runs",
    )

    # --- Fetching ---
    fetch_timeout_seconds: int = Field(
        default=30,
        ge=5,
        description="HTTP request timeout",
    )
    fetch_max_retries: int = Field(
        default=3,
        ge=1,
        description="Max retries per company fetch",
    )
    default_rate_limit_seconds: float = Field(
        default=2.0,
        ge=0.0,
        description="Default delay between requests to the same domain",
    )

    # --- Storage ---
    db_path: str = Field(
        default=str(PROJECT_ROOT / "data" / "career_tracker.db"),
        description="Path to SQLite database file",
    )

    # --- Paths ---
    companies_dir: str = Field(
        default=str(PROJECT_ROOT / "companies"),
        description="Directory containing company YAML configs",
    )
    profile_path: str = Field(
        default=str(PROJECT_ROOT / "config" / "profile.yaml"),
        description="Path to user profile YAML",
    )

    # --- Free Job API Keys ---
    adzuna_app_id: Optional[str] = Field(
        default=None,
        description="Adzuna API app ID (free tier: 100 req/day)",
    )
    adzuna_api_key: Optional[str] = Field(
        default=None,
        description="Adzuna API key",
    )
    jsearch_api_key: Optional[str] = Field(
        default=None,
        description="JSearch (RapidAPI) API key (free tier: 100 req/month)",
    )
    themuse_api_key: Optional[str] = Field(
        default=None,
        description="The Muse API key (optional — public API works without key)",
    )

    # --- Email Notifications ---
    email_to: str = Field(
        default="palulaptop@gmail.com",
        description="Target email address for job alert notifications",
    )
    smtp_host: str = Field(
        default="smtp.gmail.com",
        description="SMTP Server Host",
    )
    smtp_port: int = Field(
        default=587,
        description="SMTP Server Port",
    )
    smtp_user: Optional[str] = Field(
        default=None,
        description="SMTP Username (e.g. palulaptop@gmail.com)",
    )
    smtp_password: Optional[str] = Field(
        default=None,
        description="SMTP App Password",
    )

    @property
    def borderline_range(self) -> tuple[float, float]:
        """Score range that triggers LLM judgment (Phase 7)."""
        return (self.match_threshold_low, self.match_threshold_high)


def get_settings() -> Settings:
    """Load and return application settings (cached on first call)."""
    import os
    settings = Settings()
    if os.getenv("VERCEL"):
        settings.db_path = "/tmp/career_tracker.db"
    return settings

