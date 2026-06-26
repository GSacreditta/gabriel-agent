"""Settings for the Streamlit web app.

A pared-down version of apps/svc settings — only what the web app needs
to read the DB and identify the user via the IAP signed-header.
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


def _maybe_load_secret_manager() -> None:
    """Mirror apps/svc/app/core/secrets.py for the web subset.

    Streamlit web is a separate Cloud Run service with its own runtime SA, so
    it does its own Secret Manager pull.
    """
    if os.environ.get("USE_SECRET_MANAGER", "false").lower() != "true":
        return
    try:
        from google.cloud import secretmanager
    except ImportError:
        logger.warning("secretmanager not installed; skipping")
        return
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        return

    client = secretmanager.SecretManagerServiceClient()
    mappings = {
        "DB_PASSWORD": "db-password",
        "DB_HOST": "DB_HOST",
        "DB_PORT": "db-port",
        "DB_NAME": "db-name",
        "DB_USER": "db-user",
    }
    for env_var, secret_name in mappings.items():
        if os.environ.get(env_var):
            continue
        try:
            name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
            response = client.access_secret_version(request={"name": name})
            os.environ[env_var] = response.payload.data.decode("UTF-8").strip()
        except Exception as exc:
            logger.warning("Failed to load secret %s: %s", secret_name, exc)


_maybe_load_secret_manager()


class WebSettings(BaseSettings):
    APP_NAME: str = "SMFO"
    ENVIRONMENT: str = "dev"
    GOOGLE_CLOUD_PROJECT: Optional[str] = None
    USE_SECRET_MANAGER: bool = False

    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "smfo"
    DB_PASSWORD: SecretStr = SecretStr("")
    DB_NAME: str = "smfo"
    DB_CONNECTION_NAME: Optional[str] = None

    # IAP places the signed JWT in this header; we trust it because IAP
    # is the only ingress. The Cloud Load Balancer also adds the user
    # email in a non-signed header (`X-Goog-Authenticated-User-Email`),
    # convenient for display but NOT to be trusted alone.
    IAP_AUDIENCE: Optional[str] = None

    @property
    def database_url(self) -> str:
        pwd = self.DB_PASSWORD.get_secret_value()
        if self.DB_CONNECTION_NAME and self.DB_HOST.startswith("/cloudsql"):
            return (
                f"postgresql+psycopg2://{self.DB_USER}:{pwd}@/{self.DB_NAME}"
                f"?host={self.DB_HOST}"
            )
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{pwd}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    model_config = SettingsConfigDict(
        env_file=".env" if Path(".env").exists() else None,
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> WebSettings:
    return WebSettings()
