"""Tests for app.core.config — database_url branches + prod invariants."""

from __future__ import annotations

import pytest


def test_database_url_local_tcp(base_env):
    from app.core.config import Settings

    s = Settings()
    assert s.database_url == "postgresql+asyncpg://smfo:test-pw@localhost:5432/smfo"


def test_database_url_cloud_sql_unix_socket(base_env):
    base_env.setenv("DB_HOST", "/cloudsql/proj:us-east1:inst")
    base_env.setenv("DB_CONNECTION_NAME", "proj:us-east1:inst")
    from app.core.config import Settings

    s = Settings()
    assert s.database_url == (
        "postgresql+asyncpg://smfo:test-pw@/smfo?host=/cloudsql/proj:us-east1:inst"
    )


def test_allowed_principal_emails_list_normalises(base_env):
    base_env.setenv("ALLOWED_PRINCIPAL_EMAILS", " Gabe@SM18.com , Other@Example.com ")
    from app.core.config import Settings

    s = Settings()
    assert s.allowed_principal_emails_list == ["gabe@sm18.com", "other@example.com"]


def test_prod_missing_critical_config_raises(base_env):
    base_env.setenv("ENVIRONMENT", "prod")
    from app.core.config import get_settings

    with pytest.raises(RuntimeError) as exc:
        get_settings()
    msg = str(exc.value)
    assert "OIDC_EXPECTED_AUDIENCE" in msg
    assert "IAP_AUDIENCE" in msg
    assert "ALLOWED_PRINCIPAL_EMAILS" in msg


def test_prod_with_all_critical_config_passes(base_env):
    base_env.setenv("ENVIRONMENT", "prod")
    base_env.setenv("OIDC_EXPECTED_AUDIENCE", "https://smfo-svc-xyz.run.app")
    base_env.setenv("IAP_AUDIENCE", "/projects/123/global/backendServices/456")
    base_env.setenv("ALLOWED_PRINCIPAL_EMAILS", "gabe@example.com,daniel@example.com")
    base_env.setenv(
        "ALLOWED_PUBSUB_SERVICE_ACCOUNTS",
        "pubsub-push@proj.iam.gserviceaccount.com",
    )
    from app.core.config import get_settings

    s = get_settings()  # must not raise
    assert s.ENVIRONMENT == "prod"
