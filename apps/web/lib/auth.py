"""IAP-derived user identification.

The Streamlit app sits behind Identity-Aware Proxy. IAP adds:

- `X-Goog-Authenticated-User-Email`  — `accounts.google.com:<email>`, NOT
  signed. Convenient for display, NOT for trust.
- `X-Goog-Iap-Jwt-Assertion`         — signed JWT verifiable against IAP's
  public keys at https://www.gstatic.com/iap/verify/public_key

This module verifies the SIGNED JWT and only trusts the email derived from
its claims. The unsigned header is never the source of truth.

In non-prod environments (`ENVIRONMENT != 'prod'`), if the JWT header is
absent the loader falls back to `DEV_USER_EMAIL` for local development. In
prod that fallback is hard-disabled — missing JWT = no session.
"""

from __future__ import annotations

import os
from typing import Optional

import streamlit as st
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from lib.settings import get_settings

_IAP_PUBLIC_KEYS_URL = "https://www.gstatic.com/iap/verify/public_key"
_IAP_JWT_HEADER = "X-Goog-Iap-Jwt-Assertion"


def _read_iap_jwt() -> Optional[str]:
    try:
        # type: ignore[attr-defined]
        headers = dict(st.context.headers or {})
    except Exception:
        return None
    return headers.get(_IAP_JWT_HEADER)


def _verify_iap_jwt(jwt: str, expected_audience: str) -> Optional[dict]:
    """Verify IAP JWT against Google's public keys.

    Returns claims dict on success, None on any failure. We swallow the
    specific error and return None because Streamlit can't distinguish
    error types and the only sensible response is 'no user'.
    """
    try:
        return id_token.verify_token(
            jwt,
            google_requests.Request(),
            audience=expected_audience,
            certs_url=_IAP_PUBLIC_KEYS_URL,
        )
    except Exception:
        return None


def current_user_email() -> Optional[str]:
    """Return the verified user email, or None.

    In prod: requires a valid IAP JWT with email in the allowlist. No JWT or
    invalid JWT or off-allowlist = no session.
    In dev: falls back to DEV_USER_EMAIL when JWT is absent.
    """
    settings = get_settings()
    cached = st.session_state.get("_user_email")
    if cached:
        return cached

    jwt = _read_iap_jwt()
    email: Optional[str] = None

    if jwt and settings.IAP_AUDIENCE:
        claims = _verify_iap_jwt(jwt, settings.IAP_AUDIENCE)
        if claims:
            raw = (claims.get("email") or "").strip().lower()
            allowed = {e.strip().lower() for e in (settings.ALLOWED_PRINCIPAL_EMAILS or "").split(",") if e.strip()}
            if raw and (not allowed or raw in allowed):
                email = raw

    # Dev fallback — never active in prod.
    if not email and settings.ENVIRONMENT != "prod":
        dev_email = os.environ.get("DEV_USER_EMAIL")
        if dev_email:
            email = dev_email.strip().lower()

    if email:
        st.session_state["_user_email"] = email
    return email
