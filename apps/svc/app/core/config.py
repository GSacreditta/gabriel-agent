"""Settings for smfo-svc.

Loaded from env vars (populated either by Cloud Run / .env / Secret Manager —
see secrets.load_secrets_into_env). Cached via lru_cache so settings are read
once per process.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- App ---
    APP_NAME: str = "smfo-svc"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    PORT: int = 8082
    ENVIRONMENT: str = "dev"  # 'dev' | 'staging' | 'prod'

    # --- Google Cloud ---
    GOOGLE_CLOUD_PROJECT: Optional[str] = None
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    USE_SECRET_MANAGER: bool = False

    # --- LLM (Vertex AI Claude) ---
    VERTEX_AI_PROJECT_ID: Optional[str] = None  # defaults to GOOGLE_CLOUD_PROJECT
    VERTEX_AI_LOCATION: str = "us-east5"  # Claude on Vertex region
    ANTHROPIC_VERTEX_MODEL: str = "claude-sonnet-4-5"
    # Fallback direct Anthropic (not used in MVP path)
    ANTHROPIC_API_KEY: Optional[SecretStr] = None

    # --- Embedding (Vertex) ---
    VERTEX_EMBEDDING_MODEL: str = "text-multilingual-embedding-002"

    # --- Database (Cloud SQL via Unix socket in prod) ---
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "smfo"
    DB_PASSWORD: SecretStr = SecretStr("")
    DB_NAME: str = "smfo"
    DB_CONNECTION_NAME: Optional[str] = None  # Cloud SQL: project:region:instance

    # --- Google Drive ---
    DRIVE_MASTER_FOLDER_ID: str = "1mI0N2VXo9zQPSBq4u4dNJd4ixjUuUTZe"  # SM18_FO

    # --- FAISS (kept per plan) ---
    FAISS_PERSIST_DIRECTORY: str = "/app/faiss_db"
    FAISS_USE_CLOUD_STORAGE: bool = False
    FAISS_BUCKET_NAME: str = "gabriel-agent-faiss"

    # --- Slack ---
    SLACK_BOT_TOKEN: Optional[SecretStr] = None
    SLACK_SIGNING_SECRET: Optional[SecretStr] = None
    SLACK_APP_TOKEN: Optional[SecretStr] = None
    SLACK_DEFAULT_CHANNEL: str = "#sm18_fo"

    # --- Gmail ---
    GMAIL_CLIENT_ID: Optional[str] = None
    GMAIL_CLIENT_SECRET: Optional[SecretStr] = None
    GMAIL_CREDENTIALS_DIR: str = "/app/tmp/gmail_credentials"

    # --- OIDC (Pub/Sub authenticated push, Streamlit→API) ---
    OIDC_EXPECTED_AUDIENCE: Optional[str] = None  # e.g., the smfo-svc URL
    IAP_AUDIENCE: Optional[str] = None  # signed-header JWT audience
    # Comma-separated emails allowed to call the API directly (Streamlit user session)
    ALLOWED_PRINCIPAL_EMAILS: str = ""
    # Service-account emails allowed to OIDC-push to webhooks (Pub/Sub)
    ALLOWED_PUBSUB_SERVICE_ACCOUNTS: str = ""

    # --- Observability ---
    SENTRY_DSN: Optional[str] = None

    @property
    def database_url(self) -> str:
        """Compose an asyncpg-compatible URL.

        In Cloud Run with Cloud SQL, DB_HOST is typically the Unix socket
        directory (e.g., /cloudsql/<connection_name>). asyncpg supports
        `?host=/cloudsql/...` in the URL.
        """
        pwd = self.DB_PASSWORD.get_secret_value()
        if self.DB_CONNECTION_NAME and self.DB_HOST.startswith("/cloudsql"):
            return (
                f"postgresql+asyncpg://{self.DB_USER}:{pwd}@/{self.DB_NAME}"
                f"?host={self.DB_HOST}"
            )
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{pwd}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def allowed_principal_emails_list(self) -> list[str]:
        return [e.strip().lower() for e in self.ALLOWED_PRINCIPAL_EMAILS.split(",") if e.strip()]

    @property
    def allowed_pubsub_service_accounts_list(self) -> list[str]:
        return [s.strip().lower() for s in self.ALLOWED_PUBSUB_SERVICE_ACCOUNTS.split(",") if s.strip()]

    @property
    def effective_vertex_project(self) -> Optional[str]:
        return self.VERTEX_AI_PROJECT_ID or self.GOOGLE_CLOUD_PROJECT

    model_config = SettingsConfigDict(
        env_file=".env" if Path(".env").exists() else None,
        case_sensitive=True,
        extra="ignore",
    )


def _assert_prod_invariants(settings: "Settings") -> None:
    """Fail loud at startup if prod is missing security-critical config.

    Cloud Run sets many env vars Pydantic doesn't know about (PORT, K_REVISION,
    etc.), so we can't use extra='forbid' to catch typos directly. Instead we
    explicitly require the auth knobs to be non-empty in prod. A typo like
    `IAP_AUDIANCE=...` then surfaces as "IAP_AUDIENCE not set" at boot rather
    than as a silent auth bypass at first request.
    """
    if settings.ENVIRONMENT != "prod":
        return
    missing: list[str] = []
    if not settings.OIDC_EXPECTED_AUDIENCE:
        missing.append("OIDC_EXPECTED_AUDIENCE")
    if not settings.IAP_AUDIENCE:
        missing.append("IAP_AUDIENCE")
    if not settings.ALLOWED_PRINCIPAL_EMAILS:
        missing.append("ALLOWED_PRINCIPAL_EMAILS")
    if not settings.ALLOWED_PUBSUB_SERVICE_ACCOUNTS:
        missing.append("ALLOWED_PUBSUB_SERVICE_ACCOUNTS")
    if missing:
        raise RuntimeError(
            "Production env is missing required security config: "
            + ", ".join(missing)
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    _assert_prod_invariants(s)
    return s
