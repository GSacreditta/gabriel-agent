"""SMFO Streamlit shell — landing page.

Run locally:
    cd apps/web
    DEV_USER_EMAIL=you@example.com streamlit run Home.py

Production runs behind IAP, which gates access to the 4 allowed Google
accounts (Gabriel + Daniel + Geraldine + Vivian).
"""

from __future__ import annotations

import streamlit as st

from lib.auth import current_user_email
from lib.settings import get_settings

settings = get_settings()

st.set_page_config(
    page_title=f"{settings.APP_NAME} — Stern Mazal",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

user = current_user_email()

with st.sidebar:
    st.markdown(f"### {settings.APP_NAME}")
    if user:
        st.caption(f"Signed in as **{user}**")
    else:
        st.caption(":warning: No IAP user; running unauthenticated")
    st.caption(f"Env: `{settings.ENVIRONMENT}`")

st.title("Stern Mazal Family Office")
st.markdown(
    """
    Welcome to **SMFO** — the family office operating platform.

    Use the sidebar to navigate:

    - **Portfolio** — the three primary views (SMFO aggregate, per-vehicle, per-family).
    - More pages land in week 2-4: Documents, Senders, HDL Inbox, Taxonomy, Bulk Ops.
    """
)

st.divider()

cols = st.columns(3)
with cols[0]:
    st.metric("Reporting views", "3", help="SMFO aggregate · per-vehicle · per-family")
with cols[1]:
    st.metric("Live workflows", "0", help="Document/Email/Chat/Bulk intake — land in week 2-4")
with cols[2]:
    st.metric("HDL pending", "—", help="Will populate once intake is live")

st.caption(
    "Drive + Gmail + Slack intake autopilot is in active development. "
    "Portfolio data grows organically from those sources — no master spreadsheet import."
)
