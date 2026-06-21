"""
Application settings.

Loads configuration from the .env file using Pydantic Settings.
Import the global `settings` object anywhere in the project.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration."""

    # Environment
    APP_ENV: str = Field(default="development")
    DEBUG: bool = Field(default=True)

    # Project paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent

    # Gemini
    GEMINI_MODEL: str = Field(default="gemini-flash-lite-latest")
    GEMINI_API_KEY: SecretStr | None = None

    # Weather APIs
    OPENWEATHER_API_KEY: SecretStr | None = None
    VISUAL_CROSSING_API_KEY: SecretStr | None = None

    # Places API
    GEOAPIFY_API_KEY: SecretStr | None = None

    # Routing API
    OPENROUTESERVICE_API_KEY: SecretStr | None = None

    # Default values
    DEFAULT_CURRENCY: str = Field(default="INR")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()