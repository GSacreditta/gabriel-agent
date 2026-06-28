"""Tests for app.core.oidc — auth bypass scenarios.

These tests pin the default-DENY behavior so a regression in the allowlist
logic can't silently re-introduce the bypass we just fixed.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request


def _req(headers=None) -> Request:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
    }
    return Request(scope)


# ---- _verify_oidc_token ----------------------------------------------------


def test_audience_unset_in_dev_warns_but_proceeds(base_env):
    base_env.setenv("ENVIRONMENT", "dev")
    from app.core.config import get_settings
    from app.core.oidc import _verify_oidc_token

    s = get_settings()
    with patch(
        "app.core.oidc.id_token.verify_oauth2_token", return_value={"email": "ok@x.com"}
    ):
        claims = _verify_oidc_token("fake", None, s)
        assert claims["email"] == "ok@x.com"


def test_audience_unset_in_prod_raises_503(base_env):
    base_env.setenv("ENVIRONMENT", "prod")
    base_env.setenv("OIDC_EXPECTED_AUDIENCE", "https://x.run.app")
    base_env.setenv("IAP_AUDIENCE", "/projects/1/global/backendServices/2")
    base_env.setenv("ALLOWED_PRINCIPAL_EMAILS", "a@b.com")
    base_env.setenv("ALLOWED_PUBSUB_SERVICE_ACCOUNTS", "sa@p.iam.gserviceaccount.com")
    from app.core.config import get_settings
    from app.core.oidc import _verify_oidc_token

    s = get_settings()
    with pytest.raises(HTTPException) as exc:
        _verify_oidc_token("fake", None, s)
    assert exc.value.status_code == 503


def test_invalid_token_raises_401(base_env):
    from app.core.config import get_settings
    from app.core.oidc import _verify_oidc_token

    s = get_settings()
    with patch(
        "app.core.oidc.id_token.verify_oauth2_token",
        side_effect=ValueError("bad signature"),
    ):
        with pytest.raises(HTTPException) as exc:
            _verify_oidc_token("fake", "aud", s)
        assert exc.value.status_code == 401


# ---- require_pubsub_oidc ---------------------------------------------------


def test_pubsub_missing_auth_header_raises_401(base_env):
    base_env.setenv("ALLOWED_PUBSUB_SERVICE_ACCOUNTS", "sa@p.iam.gserviceaccount.com")
    from app.core.config import get_settings
    from app.core.oidc import require_pubsub_oidc

    with pytest.raises(HTTPException) as exc:
        require_pubsub_oidc(_req(), get_settings())
    assert exc.value.status_code == 401


def test_pubsub_token_without_email_raises_401(base_env):
    base_env.setenv("OIDC_EXPECTED_AUDIENCE", "aud")
    base_env.setenv("ALLOWED_PUBSUB_SERVICE_ACCOUNTS", "sa@p.iam.gserviceaccount.com")
    from app.core.config import get_settings
    from app.core.oidc import require_pubsub_oidc

    with patch(
        "app.core.oidc.id_token.verify_oauth2_token", return_value={"sub": "x"}
    ):
        with pytest.raises(HTTPException) as exc:
            require_pubsub_oidc(
                _req({"Authorization": "Bearer x"}), get_settings()
            )
        assert exc.value.status_code == 401


def test_pubsub_email_not_in_allowlist_raises_403(base_env):
    base_env.setenv("OIDC_EXPECTED_AUDIENCE", "aud")
    base_env.setenv("ALLOWED_PUBSUB_SERVICE_ACCOUNTS", "allowed@p.iam.gserviceaccount.com")
    from app.core.config import get_settings
    from app.core.oidc import require_pubsub_oidc

    with patch(
        "app.core.oidc.id_token.verify_oauth2_token",
        return_value={"email": "attacker@evil.com"},
    ):
        with pytest.raises(HTTPException) as exc:
            require_pubsub_oidc(
                _req({"Authorization": "Bearer x"}), get_settings()
            )
        assert exc.value.status_code == 403


def test_pubsub_empty_allowlist_in_prod_raises_503(base_env):
    """Default-DENY: empty allowlist in prod must not silently allow."""
    base_env.setenv("ENVIRONMENT", "prod")
    base_env.setenv("OIDC_EXPECTED_AUDIENCE", "aud")
    base_env.setenv("IAP_AUDIENCE", "iap-aud")
    base_env.setenv("ALLOWED_PRINCIPAL_EMAILS", "a@b.com")
    base_env.setenv("ALLOWED_PUBSUB_SERVICE_ACCOUNTS", "x@p.iam.gserviceaccount.com")
    from app.core.config import get_settings
    from app.core.oidc import require_pubsub_oidc

    s = get_settings()
    # Clear the prod-loaded allowlist to simulate a misconfig at runtime.
    object.__setattr__(s, "ALLOWED_PUBSUB_SERVICE_ACCOUNTS", "")
    with patch(
        "app.core.oidc.id_token.verify_oauth2_token",
        return_value={"email": "anything@example.com"},
    ):
        with pytest.raises(HTTPException) as exc:
            require_pubsub_oidc(_req({"Authorization": "Bearer x"}), s)
        assert exc.value.status_code == 503


def test_pubsub_valid_token_in_allowlist_succeeds(base_env):
    base_env.setenv("OIDC_EXPECTED_AUDIENCE", "aud")
    base_env.setenv("ALLOWED_PUBSUB_SERVICE_ACCOUNTS", "sa@p.iam.gserviceaccount.com")
    from app.core.config import get_settings
    from app.core.oidc import require_pubsub_oidc

    with patch(
        "app.core.oidc.id_token.verify_oauth2_token",
        return_value={"email": "sa@p.iam.gserviceaccount.com"},
    ):
        claims = require_pubsub_oidc(
            _req({"Authorization": "Bearer x"}), get_settings()
        )
        assert claims["email"] == "sa@p.iam.gserviceaccount.com"


# ---- require_principal_oidc -----------------------------------------------


def test_principal_audience_falls_back_to_oidc_expected(base_env):
    base_env.setenv("OIDC_EXPECTED_AUDIENCE", "svc-url")
    base_env.setenv("ALLOWED_PRINCIPAL_EMAILS", "gabe@sm18.com")
    from app.core.config import get_settings
    from app.core.oidc import require_principal_oidc

    captured = {}

    def _verify(_t, _req, audience):
        captured["aud"] = audience
        return {"email": "gabe@sm18.com"}

    with patch(
        "app.core.oidc.id_token.verify_oauth2_token", side_effect=_verify
    ):
        require_principal_oidc(_req({"Authorization": "Bearer x"}), get_settings())
    assert captured["aud"] == "svc-url"


def test_principal_email_not_in_allowlist_raises_403(base_env):
    base_env.setenv("IAP_AUDIENCE", "iap-aud")
    base_env.setenv("ALLOWED_PRINCIPAL_EMAILS", "gabe@sm18.com")
    from app.core.config import get_settings
    from app.core.oidc import require_principal_oidc

    with patch(
        "app.core.oidc.id_token.verify_oauth2_token",
        return_value={"email": "intruder@example.com"},
    ):
        with pytest.raises(HTTPException) as exc:
            require_principal_oidc(
                _req({"Authorization": "Bearer x"}), get_settings()
            )
        assert exc.value.status_code == 403
