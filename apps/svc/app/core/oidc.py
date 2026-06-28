"""OIDC token verification for webhook endpoints.

Two trust paths:

1. **Pub/Sub authenticated push** (Drive / Gmail webhooks): Pub/Sub attaches
   `Authorization: Bearer <id_token>` signed by a service account configured
   on the push subscription. We verify the JWT and confirm the email claim
   matches one of ALLOWED_PUBSUB_SERVICE_ACCOUNTS.

2. **Streamlit → API** (user-driven calls): the UI sends a Google ID token
   from the signed-in user's session. We verify and confirm the email is in
   ALLOWED_PRINCIPAL_EMAILS.

The audience claim is checked against OIDC_EXPECTED_AUDIENCE (typically the
Cloud Run service URL) or IAP_AUDIENCE for IAP-fronted traffic.

Slack signing-secret verification is NOT done here — Slack Bolt handles that
internally on the Slack router.
"""

from __future__ import annotations

from typing import Literal

from fastapi import Depends, HTTPException, Request, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_AuthKind = Literal["pubsub", "principal"]


def _extract_bearer(request: Request) -> str:
    auth = request.headers.get("Authorization") or request.headers.get("authorization")
    if not auth or not auth.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
        )
    return auth.split(" ", 1)[1].strip()


def _verify_oidc_token(token: str, expected_audience: str | None, settings: Settings) -> dict:
    """Verify a Google OIDC token.

    expected_audience MUST be non-empty in production. google's
    verify_oauth2_token treats audience=None as 'skip audience check', so
    accepting None in prod is an auth bypass.
    """
    if not expected_audience:
        if settings.ENVIRONMENT == "prod":
            logger.error("oidc_audience_unset_in_prod")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OIDC audience not configured",
            )
        logger.warning("oidc_audience_unset_dev_mode")
    try:
        claims = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            audience=expected_audience,
        )
    except ValueError as exc:
        logger.warning("oidc_verify_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OIDC token",
        ) from exc
    return claims


def _enforce_allowlist(
    email: str,
    allowed: list[str],
    settings: Settings,
    kind: str,
) -> None:
    """Default-DENY allowlist enforcement.

    Empty allowlist + prod = reject. Empty allowlist + non-prod = warn and
    allow (so dev/staging don't need full configuration). Email not on
    non-empty allowlist = reject in any environment.
    """
    if not allowed:
        if settings.ENVIRONMENT == "prod":
            logger.error(f"{kind}_allowlist_empty_in_prod")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"{kind} allowlist not configured",
            )
        logger.warning(f"{kind}_allowlist_empty_dev_mode")
        return
    if email not in allowed:
        # Hash the email for the log to reduce PII exposure while keeping
        # the rejection diagnosable via a known-allowlist hash table.
        logger.warning(f"{kind}_email_not_allowed", email_hash=hash(email))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{kind} not authorised",
        )


def require_pubsub_oidc(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict:
    """FastAPI dependency for Pub/Sub authenticated push receivers."""
    token = _extract_bearer(request)
    claims = _verify_oidc_token(token, settings.OIDC_EXPECTED_AUDIENCE, settings)

    email = (claims.get("email") or "").lower()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OIDC token missing email claim",
        )

    _enforce_allowlist(
        email, settings.allowed_pubsub_service_accounts_list, settings, "pubsub"
    )
    logger.debug("pubsub_oidc_ok", email_hash=hash(email))
    return claims


def require_principal_oidc(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict:
    """FastAPI dependency for Streamlit-originated user requests."""
    token = _extract_bearer(request)
    audience = settings.IAP_AUDIENCE or settings.OIDC_EXPECTED_AUDIENCE
    claims = _verify_oidc_token(token, audience, settings)

    email = (claims.get("email") or "").lower()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OIDC token missing email claim",
        )

    _enforce_allowlist(
        email, settings.allowed_principal_emails_list, settings, "principal"
    )
    logger.debug("principal_oidc_ok", email_hash=hash(email))
    return claims
