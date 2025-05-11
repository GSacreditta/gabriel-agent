from pydantic_settings import BaseSettings
from functools import lru_cache
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    # API Keys
    OPENAI_API_KEY: str
    SUPABASE_URL: str | None = None
    SUPABASE_KEY: str | None = None
    
    # OpenAI Configuration
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    
    # Google Cloud
    GOOGLE_CLOUD_PROJECT_ID: str | None = None
    GOOGLE_APPLICATION_CREDENTIALS: str | None = None
    GOOGLE_DRIVE_FOLDER_ID: str = "1mI0N2VXo9zQPSBq4u4dNJd4ixjUuUTZe"  # SM18_FO folder
    
    # Application
    APP_NAME: str = "Gabriel Agent Task Flow"
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"

    def get_google_credentials_path(self) -> Path:
        """Get the absolute path to the Google credentials file."""
        base_dir = Path(__file__).resolve().parent.parent.parent
        return base_dir / "config" / "credentials" / "location-19291-fb284eccae8d.json"

@lru_cache()
def get_settings():
    logger.debug("Loading settings from environment variables...")
    try:
        settings = Settings()
        logger.debug("Environment variables loaded successfully")
        # Log available settings (safely)
        logger.debug(f"OPENAI_API_KEY: {'[SET]' if settings.OPENAI_API_KEY else '[NOT SET]'}")
        logger.debug(f"SUPABASE_URL: {'[SET]' if settings.SUPABASE_URL else '[NOT SET]'}")
        logger.debug(f"SUPABASE_KEY: {'[SET]' if settings.SUPABASE_KEY else '[NOT SET]'}")
        logger.debug(f"GOOGLE_CLOUD_PROJECT_ID: {'[SET]' if settings.GOOGLE_CLOUD_PROJECT_ID else '[NOT SET]'}")
        logger.debug(f"GOOGLE_APPLICATION_CREDENTIALS: {'[SET]' if settings.GOOGLE_APPLICATION_CREDENTIALS else '[NOT SET]'}")
        logger.debug(f"GOOGLE_DRIVE_FOLDER_ID: {settings.GOOGLE_DRIVE_FOLDER_ID}")
        return settings
    except Exception as e:
        logger.error(f"Error loading settings: {str(e)}")
        raise 