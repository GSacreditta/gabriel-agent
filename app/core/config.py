from pydantic_settings import BaseSettings
from functools import lru_cache
import os
from pathlib import Path
import logging
from typing import Optional, List
from pydantic import SecretStr, PostgresDsn



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
    
    # Gmail API Configuration
    GMAIL_CLIENT_ID: Optional[str] = None
    GMAIL_CLIENT_SECRET: Optional[str] = None
    GMAIL_CREDENTIALS_DIR: str = "config/credentials"
    
    # Application
    APP_NAME: str = "Gabriel Agent Task Flow"
    DEBUG: bool = True
    
    # Slack settings
    SLACK_BOT_TOKEN: Optional[str] = None
    SLACK_SIGNING_SECRET: Optional[str] = None
    SLACK_APP_TOKEN: Optional[str] = None
    SLACK_DEFAULT_CHANNEL: str = "general"
    
    # Ngrok settings
    NGROK_AUTH_TOKEN: Optional[str] = None
    NGROK_DOMAIN: Optional[str] = None
    PUBLIC_URL: Optional[str] = None 
    
    # Scheduler settings
    SCHEDULER_SCAN_INTERVAL: int = 300  # 5 minutes in seconds
    
    # Directory settings
    TEMP_DIR: str = "temp"  # Default temporary directory

    # FAISS Vector Storage settings
    FAISS_PERSIST_DIRECTORY: str = "/app/faiss_db"
    FAISS_USE_CLOUD_STORAGE: bool = False
    FAISS_BUCKET_NAME: str = "gabriel-agent-faiss"

    # File processing settings
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB in bytes
    ALLOWED_FILE_TYPES: str = "pdf,docx,txt"
    FILE_PROCESSING_TIMEOUT: int = 300
    BATCH_SIZE: int = 10

    # Monitoring settings
    ENABLE_TELEMETRY: bool = False
    METRICS_PORT: int = 9090
    HEALTH_CHECK_INTERVAL: int = 60

    # Cache settings
    CACHE_TTL: int = 3600
    CACHE_MAX_SIZE: int = 1000
    ENABLE_RESPONSE_CACHE: bool = True

    # Rate limiting settings
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60
    RATE_LIMIT_STRATEGY: str = "fixed-window"
    
    # Database Configuration
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: SecretStr
    DB_NAME: str
    DB_CONNECTION_NAME: Optional[str] = None # For Cloud SQL Proxy, if used
    DATABASE_URL: Optional[PostgresDsn] = None # Can be provided directly or assembled


    class Config:
        env_file = ".env"
        case_sensitive = True

    def get_google_credentials_path(self) -> str:
        """Get the path to Google credentials file."""
        if not self.GOOGLE_APPLICATION_CREDENTIALS:
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS not set")
        return self.GOOGLE_APPLICATION_CREDENTIALS
        
    @property
    def allowed_file_types_list(self) -> List[str]:
        """Get allowed file types as a list."""
        return [ft.strip() for ft in self.ALLOWED_FILE_TYPES.split(",")]

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