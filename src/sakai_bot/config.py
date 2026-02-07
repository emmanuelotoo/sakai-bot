"""
Configuration management for Sakai Monitoring Bot.

Loads and validates all required environment variables with clear error messages.
Uses Pydantic Settings for type safety and validation.
"""

import logging
from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    All required variables must be set, or the application will fail fast
    with a clear error message indicating which variables are missing.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Sakai LMS Configuration
    sakai_base_url: str = Field(
        default="https://sakai.ug.edu.gh",
        description="Base URL for Sakai LMS instance"
    )
    sakai_username: str = Field(
        ...,
        description="Sakai login username (student ID)"
    )
    sakai_password: str = Field(
        ...,
        description="Sakai login password"
    )
    
    # Supabase Configuration
    supabase_url: str = Field(
        ...,
        description="Supabase project URL"
    )
    supabase_service_role_key: str = Field(
        ...,
        description="Supabase service role key (not anon key)"
    )
    
    # Telegram Bot API Configuration
    telegram_bot_token: str = Field(
        ...,
        description="Telegram Bot API token (from @BotFather)"
    )
    telegram_chat_id: str = Field(
        ...,
        description="Telegram chat ID (user, group, or channel)"
    )
    
    # Optional Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    timezone: str = Field(
        default="Africa/Accra",
        description="Timezone for date parsing"
    )
    current_semester: Optional[str] = Field(
        default=None,
        description="Filter courses to this semester (e.g., 'S1-2526'). If not set, all courses are scraped."
    )
    course_level_filter: Optional[int] = Field(
        default=None,
        description="Only include courses at or above this level (e.g., 300 for 300-level). Matches the first digit of the course number."
    )
    
    @field_validator("sakai_base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Ensure base URL doesn't have trailing slash."""
        return v.rstrip("/")
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Ensure log level is valid."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return upper
    
    @property
    def sakai_login_url(self) -> str:
        """Full URL for Sakai login form submission."""
        return f"{self.sakai_base_url}/portal/xlogin"
    
    @property
    def sakai_portal_url(self) -> str:
        """URL for Sakai portal (post-login landing)."""
        return f"{self.sakai_base_url}/portal"


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached application settings.
    
    Returns:
        Settings: Validated application settings
        
    Raises:
        ValidationError: If required environment variables are missing or invalid
    """
    return Settings()


def setup_logging(settings: Optional[Settings] = None) -> logging.Logger:
    """
    Configure application logging.
    
    Args:
        settings: Optional settings instance, will be loaded if not provided
        
    Returns:
        logging.Logger: Configured logger instance
    """
    if settings is None:
        settings = get_settings()
    
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    return logging.getLogger("sakai_bot")
