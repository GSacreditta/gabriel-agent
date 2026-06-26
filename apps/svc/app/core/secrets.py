"""Google Cloud Secret Manager loader.

When `USE_SECRET_MANAGER=true`, this module pulls named secrets from Secret Manager
and writes them into the process environment so the `Settings` class (which only
reads `os.environ`) picks them up. When false, settings load from .env or shell env.

Mirrors the secret name convention used by the legacy `gabriel-agent` service so
the same Secret Manager entries can be reused without re-provisioning.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# env_var_name -> secret_manager_secret_name
# These names MUST exist in the GCP project's Secret Manager.
_SECRET_MAPPINGS: dict[str, str] = {
    # Anthropic / Vertex
    "ANTHROPIC_API_KEY": "anthropic-api-key",  # only if using direct Anthropic
    # Database
    "DB_PASSWORD": "db-password",
    "DB_HOST": "DB_HOST",  # legacy: secret name matches env var
    "DB_PORT": "db-port",
    "DB_NAME": "db-name",
    "DB_USER": "db-user",
    # Slack
    "SLACK_BOT_TOKEN": "slack-bot-token",
    "SLACK_SIGNING_SECRET": "slack-signing-secret",
    "SLACK_APP_TOKEN": "slack-app-token",
    # Gmail OAuth
    "GMAIL_CLIENT_ID": "gmail-client-id",
    "GMAIL_CLIENT_SECRET": "gmail-client-secret",
    # IAP audience (for OIDC token validation on Streamlit→API path)
    "IAP_AUDIENCE": "iap-audience",
}


def _load_one(client, project_id: str, secret_name: str) -> Optional[str]:
    try:
        name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8").strip()
    except Exception as exc:
        logger.warning("Failed to load secret %s: %s", secret_name, exc)
        return None


def load_secrets_into_env() -> None:
    """Populate os.environ from Secret Manager when USE_SECRET_MANAGER=true.

    Skipped silently in dev / local. Secrets already set in the environment
    (e.g., via Cloud Run secretKeyRef) are not overwritten.
    """
    if os.environ.get("USE_SECRET_MANAGER", "false").lower() != "true":
        logger.info("USE_SECRET_MANAGER=false; using env vars only")
        return

    try:
        from google.cloud import secretmanager
    except ImportError:
        logger.error("google-cloud-secret-manager not installed; cannot load secrets")
        return

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        logger.error("GOOGLE_CLOUD_PROJECT not set; cannot resolve Secret Manager")
        return

    client = secretmanager.SecretManagerServiceClient()

    # Optional aggregate config blob
    app_config = _load_one(client, project_id, "smfo-app-config")
    if app_config:
        try:
            for key, value in json.loads(app_config).items():
                env_key = key.upper()
                if not os.environ.get(env_key) and value is not None:
                    os.environ[env_key] = str(value)
        except json.JSONDecodeError:
            logger.warning("smfo-app-config is not valid JSON; skipping")

    # Google service account credentials (write to /tmp and point env at file)
    google_creds = _load_one(client, project_id, "google-service-account-key")
    if google_creds:
        creds_path = "/tmp/google_credentials.json"
        with open(creds_path, "w", encoding="utf-8") as f:
            f.write(google_creds)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path

    loaded = 0
    for env_var, secret_name in _SECRET_MAPPINGS.items():
        if os.environ.get(env_var):
            continue  # already provided (e.g., by Cloud Run secretKeyRef)
        value = _load_one(client, project_id, secret_name)
        if value:
            os.environ[env_var] = value
            loaded += 1

    logger.info("Loaded %d secrets from Secret Manager", loaded)
