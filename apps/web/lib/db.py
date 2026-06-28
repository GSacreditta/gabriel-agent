"""Database access for the Streamlit web app.

Uses a single cached SQLAlchemy engine. Queries return pandas DataFrames.
The web app reads ONLY — writes happen via smfo-svc (the API service) so
that workflow checkpointing and audit stays in one place.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from lib.settings import get_settings


@st.cache_resource
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, future=True, pool_pre_ping=True)


def read_sql(query: str, params: dict | None = None) -> pd.DataFrame:
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params=params or {})


# ---- View accessors -------------------------------------------------------

def smfo_aggregate() -> pd.DataFrame:
    return read_sql(
        """
        SELECT asset_class,
               liquidity_type,
               sub_category,
               total_value,
               total_commitment,
               total_funded,
               investment_count
        FROM v_smfo_aggregate
        ORDER BY asset_class, liquidity_type, sub_category
        """
    )


def per_vehicle() -> pd.DataFrame:
    return read_sql(
        """
        SELECT vehicle,
               investment,
               asset_class,
               liquidity_type,
               commitment_amount,
               funded_amount,
               current_value,
               ownership_pct,
               structure
        FROM v_per_vehicle
        ORDER BY vehicle, investment
        """
    )


def per_family() -> pd.DataFrame:
    return read_sql(
        """
        SELECT branch,
               asset_class,
               attributed_value,
               attributed_commitment,
               investment_count
        FROM v_per_family
        ORDER BY branch, asset_class
        """
    )
