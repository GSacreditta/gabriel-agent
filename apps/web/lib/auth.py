"""IAP-derived user identification.

The Streamlit app sits behind Identity-Aware Proxy. IAP adds two headers
to every authenticated request:

- `X-Goog-Authenticated-User-Email`  — `accounts.google.com:<email>`, NOT
  signed; convenient for display only.
- `X-Goog-Iap-Jwt-Assertion`         — signed JWT, verifiable against
  Google's public keys. For sensitive paths we should verify; for the MVP
  read-only portfolio view, the unsigned email header is sufficient since
  IAP is the only ingress and the principle of defence-in-depth is met
  by the runtime IAM on the Cloud Run service.

When running locally without IAP, falls back to a `DEV_USER_EMAIL` env var.
"""

from __future__ import annotations

import os
from typing import Optional

import streamlit as st


def _strip_prefix(header: str | None) -> str | None:
    if not header:
        return None
    # IAP format: 'accounts.google.com:gabriel@example.com'
    if ":" in header:
        return header.split(":", 1)[1].strip().lower()
    return header.strip().lower()


def current_user_email() -> Optional[str]:
    """Best-effort lookup of the authenticated user's email."""
    # Streamlit's session_state can cache for the duration of the session.
    cached = st.session_state.get("_user_email")
    if cached:
        return cached

    # Streamlit exposes inbound HTTP headers via st.context.headers (Streamlit
    # >= 1.37). Older versions don't, so we try both.
    headers: dict[str, str] = {}
    try:
        # type: ignore[attr-defined]
        headers = dict(st.context.headers or {})
    except Exception:
        headers = {}

    email = _strip_prefix(headers.get("X-Goog-Authenticated-User-Email"))

    if not email:
        email = os.environ.get("DEV_USER_EMAIL")  # local dev fallback

    if email:
        st.session_state["_user_email"] = email
    return email
