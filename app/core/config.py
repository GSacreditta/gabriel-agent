from pydantic_settings import BaseSettings
from functools import lru_cache
import os
from pathlib import Path
import logging
from typing import Optional

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
    
    # Slack settings
    SLACK_BOT_TOKEN: Optional[str] = None
    SLACK_SIGNING_SECRET: Optional[str] = None
    SLACK_APP_TOKEN: Optional[str] = None
    SLACK_DEFAULT_CHANNEL: Optional[str] = None
    
    # Ngrok settings
    NGROK_AUTH_TOKEN: Optional[str] = None
    NGROK_DOMAIN: Optional[str] = None
    PUBLIC_URL: Optional[str] = None 
    
    class Config:
        env_file = ".env"
        case_sensitive = True

    def get_google_credentials_path(self) -> Path:
        """Get the absolute path to the Google credentials file."""
        try:
            # First try to use the environment variable if set
            if self.GOOGLE_APPLICATION_CREDENTIALS:
                creds_path = Path(self.GOOGLE_APPLICATION_CREDENTIALS)
                if creds_path.is_file() and creds_path.exists():
                    return creds_path
                else:
                    logger.warning(f"Credentials file not found at {creds_path}, falling back to default location")
            
            # Fallback to default location
            base_dir = Path(__file__).resolve().parent.parent.parent
            creds_path = base_dir / "config" / "credentials" / "location-19291-fb284eccae8d.json"
            
            if not creds_path.exists():
                raise FileNotFoundError(f"Google credentials file not found at {creds_path}")
            
            # Verify we can read the file
            if not os.access(creds_path, os.R_OK):
                raise PermissionError(f"No read permission for credentials file at {creds_path}")
                
            return creds_path
        except Exception as e:
            logger.error(f"Error accessing Google credentials: {str(e)}")
            raise

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