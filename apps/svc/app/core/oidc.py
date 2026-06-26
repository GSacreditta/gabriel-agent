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


def _verify_oidc_token(token: str, expected_audience: str | None) -> dict:
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


def require_pubsub_oidc(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict:
    """FastAPI dependency for Pub/Sub authenticated push receivers."""
    token = _extract_bearer(request)
    audience = settings.OIDC_EXPECTED_AUDIENCE
    claims = _verify_oidc_token(token, audience)

    email = (claims.get("email") or "").lower()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OIDC token missing email claim",
        )

    allowed = settings.allowed_pubsub_service_accounts_list
    if allowed and email not in allowed:
        logger.warning("pubsub_email_not_allowed", email=email)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Service account not authorised",
        )

    logger.debug("pubsub_oidc_ok", email=email)
    return claims


def require_principal_oidc(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict:
    """FastAPI dependency for Streamlit-originated user requests."""
    token = _extract_bearer(request)
    audience = settings.IAP_AUDIENCE or settings.OIDC_EXPECTED_AUDIENCE
    claims = _verify_oidc_token(token, audience)

    email = (claims.get("email") or "").lower()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OIDC token missing email claim",
        )

    allowed = settings.allowed_principal_emails_list
    if allowed and email not in allowed:
        logger.warning("principal_email_not_allowed", email=email)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not on principal allowlist",
        )

    logger.debug("principal_oidc_ok", email=email)
    return claims
