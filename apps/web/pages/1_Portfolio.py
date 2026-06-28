"""Portfolio — three reporting views.

A: SMFO aggregate (primary, decision-making view).
B: Per-vehicle (compliance, K-1s, tax prep).
C: Per-family rollup (Sternberg-Roth / Sternberg-Pardo) using the vehicle-level
   family_branch_id tag. Shared vehicles (e.g., SM18 LLC, 7Stern) appear only
   in views A + B — by design.
"""

from __future__ import annotations

import streamlit as st

from lib import db
from lib.auth import current_user_email

st.set_page_config(page_title="Portfolio — SMFO", page_icon="📊", layout="wide")

user = current_user_email()
with st.sidebar:
    if user:
        st.caption(f"Signed in as **{user}**")

st.title("📊 Portfolio")

tab_a, tab_b, tab_c = st.tabs(
    [
        "SMFO aggregate",
        "Per-vehicle",
        "Per-family (Roth / Pardo)",
    ]
)


def _money(label: str):
    return st.column_config.NumberColumn(label=label, format="$%,.0f")


# ---- View A: SMFO aggregate -------------------------------------------------
with tab_a:
    st.subheader("Stern Mazal aggregate")
    st.caption(
        "Everything across every vehicle, by asset class + liquidity. "
        "This is the primary decision-making view."
    )
    try:
        df = db.smfo_aggregate()
    except Exception as exc:
        st.error(f"Failed to query v_smfo_aggregate: {exc}")
        df = None

    if df is None:
        pass
    elif df.empty:
        st.info(
            "No active investment positions yet. Portfolio grows organically as "
            "documents and emails are ingested."
        )
    else:
        cols = st.columns(4)
        cols[0].metric(
            "Total value",
            f"${df['total_value'].fillna(0).sum():,.0f}",
        )
        cols[1].metric(
            "Total commitment",
            f"${df['total_commitment'].fillna(0).sum():,.0f}",
        )
        cols[2].metric(
            "Total funded",
            f"${df['total_funded'].fillna(0).sum():,.0f}",
        )
        cols[3].metric(
            "Investments",
            int(df["investment_count"].fillna(0).sum()),
        )
        st.dataframe(
            df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "total_value": _money("Value"),
                "total_commitment": _money("Commitment"),
                "total_funded": _money("Funded"),
            },
        )


# ---- View B: Per-vehicle ----------------------------------------------------
with tab_b:
    st.subheader("Per-vehicle")
    st.caption("One row per active position. Compliance, K-1s, tax prep.")
    try:
        df = db.per_vehicle()
    except Exception as exc:
        st.error(f"Failed to query v_per_vehicle: {exc}")
        df = None

    if df is None:
        pass
    elif df.empty:
        st.info("No positions yet.")
    else:
        vehicles = ["(all)"] + sorted(df["vehicle"].dropna().unique().tolist())
        choice = st.selectbox("Vehicle", vehicles, index=0)
        filtered = df if choice == "(all)" else df[df["vehicle"] == choice]
        st.dataframe(
            filtered,
            hide_index=True,
            use_container_width=True,
            column_config={
                "commitment_amount": _money("Commitment"),
                "funded_amount": _money("Funded"),
                "current_value": _money("Value"),
            },
        )


# ---- View C: Per-family -----------------------------------------------------
with tab_c:
    st.subheader("Per-family rollup")
    st.caption(
        "Vehicles tagged with a family branch (`sternberg_roth` or "
        "`sternberg_pardo`). Shared vehicles (no family tag — e.g., SM18 LLC, "
        "7Stern) are intentionally excluded here; they live in the SMFO aggregate."
    )
    try:
        df = db.per_family()
    except Exception as exc:
        st.error(f"Failed to query v_per_family: {exc}")
        df = None

    if df is None:
        pass
    elif df.empty:
        st.info(
            "Per-family view is empty. Tag vehicles with `family_branch:` in "
            "config/vehicles.yaml and re-seed, or wait for organic data."
        )
    else:
        for branch in sorted(df["branch"].unique()):
            sub = df[df["branch"] == branch]
            st.markdown(f"### {branch.replace('_', '-').title()}")
            cols = st.columns(3)
            cols[0].metric(
                "Attributed value",
                f"${sub['attributed_value'].fillna(0).sum():,.0f}",
            )
            cols[1].metric(
                "Attributed commitment",
                f"${sub['attributed_commitment'].fillna(0).sum():,.0f}",
            )
            cols[2].metric(
                "Investments",
                int(sub["investment_count"].fillna(0).sum()),
            )
            st.dataframe(
                sub.drop(columns=["branch"]),
                hide_index=True,
                use_container_width=True,
                column_config={
                    "attributed_value": _money("Value"),
                    "attributed_commitment": _money("Commitment"),
                },
            )
