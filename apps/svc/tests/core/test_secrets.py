"""Tests for app.core.secrets — silent-fallback paths + app_config allowlist."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest


def test_disabled_is_noop(base_env):
    """USE_SECRET_MANAGER=false skips all SM calls."""
    base_env.setenv("USE_SECRET_MANAGER", "false")
    from app.core import secrets

    sm_client = MagicMock()
    with patch(
        "google.cloud.secretmanager.SecretManagerServiceClient",
        return_value=sm_client,
    ):
        secrets.load_secrets_into_env()
    sm_client.access_secret_version.assert_not_called()


def test_enabled_without_project_id_skips_loudly(base_env, caplog):
    base_env.setenv("USE_SECRET_MANAGER", "true")
    base_env.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    from app.core import secrets

    with caplog.at_level("ERROR"):
        secrets.load_secrets_into_env()
    assert any("GOOGLE_CLOUD_PROJECT" in r.message for r in caplog.records)


def test_existing_env_var_not_overwritten(base_env):
    base_env.setenv("USE_SECRET_MANAGER", "true")
    base_env.setenv("GOOGLE_CLOUD_PROJECT", "p")
    base_env.setenv("DB_PASSWORD", "already-set-locally")
    from app.core import secrets

    with patch.object(secrets, "_load_one", return_value="from-secret-manager"):
        with patch("google.cloud.secretmanager.SecretManagerServiceClient"):
            secrets.load_secrets_into_env()
    assert os.environ["DB_PASSWORD"] == "already-set-locally"


def test_app_config_allowlist_drops_unknown_keys(base_env, caplog):
    base_env.setenv("USE_SECRET_MANAGER", "true")
    base_env.setenv("GOOGLE_CLOUD_PROJECT", "p")
    for k in ("PYTHONPATH", "DEBUG", "SLACK_DEFAULT_CHANNEL"):
        base_env.delenv(k, raising=False)
    from app.core import secrets

    poisoned = json.dumps({
        "PYTHONPATH": "/attacker/code",       # NOT on allowlist — drop
        "DEBUG": "true",                      # NOT on allowlist — drop
        "SLACK_DEFAULT_CHANNEL": "#evil",     # ON allowlist — accept
    })

    def _load(_client, _proj, name):
        return poisoned if name == "smfo-app-config" else None

    with patch.object(secrets, "_load_one", side_effect=_load):
        with patch("google.cloud.secretmanager.SecretManagerServiceClient"):
            with caplog.at_level("WARNING"):
                secrets.load_secrets_into_env()

    assert "PYTHONPATH" not in os.environ
    assert "DEBUG" not in os.environ
    assert os.environ["SLACK_DEFAULT_CHANNEL"] == "#evil"
    # And the drops were logged so an operator can see what was rejected.
    assert any("smfo_app_config_key_not_allowed" in r.message for r in caplog.records)
