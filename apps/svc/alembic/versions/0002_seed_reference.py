"""seed reference data — family branches, principals, vehicle types, asset taxonomy

Revision ID: 0002_seed_reference
Revises: 0001_initial
Create Date: 2026-06-24

Idempotent inserts of the foundational reference data:
- 2 family branches (Sternberg-Roth, Sternberg-Pardo)
- 4 principals (Gabriel + Geraldine, Daniel + Vivian) — brothers as approvers
- 4 vehicle types
- 7 asset classes
- Sub-categories for Cash / Fixed Income / Equity / Alternative / Currencies-Crypto
  (Commodities and Real Estate get 'Other' only; grow organically via HDL)

Downgrade removes only this seed (by slug) — does not touch user-added rows.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0002_seed_reference"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (slug, display_name)
_FAMILY_BRANCHES = [
    ("sternberg_roth", "Sternberg-Roth"),
    ("sternberg_pardo", "Sternberg-Pardo"),
]

# (full_name, surname_at_birth, role, branch_slug, is_approver)
_PRINCIPALS = [
    ("Gabriel Sternberg", "Sternberg", "principal", "sternberg_roth", True),
    ("Geraldine Roth",    "Roth",       "spouse",    "sternberg_roth", False),
    ("Daniel Sternberg",  "Sternberg", "principal", "sternberg_pardo", True),
    ("Vivian Pardo",      "Pardo",     "spouse",    "sternberg_pardo", False),
]

_VEHICLE_TYPES = [
    ("irrevocable_trust", "Irrevocable Trust"),
    ("llc",               "LLC"),
    ("personal_account",  "Personal Account"),
    ("operational_llc",   "Operational LLC"),
]

# (slug, display_name, sort_order)
_ASSET_CLASSES = [
    ("cash",              "Cash",              10),
    ("fixed_income",      "Fixed Income",      20),
    ("equity",            "Equity",            30),
    ("alternative",       "Alternative",       40),
    ("currencies_crypto", "Currencies/Crypto", 50),
    ("commodities",       "Commodities",       60),
    ("real_estate",       "Real Estate",       70),
]

# (parent_class_slug, slug, display_name, sort_order)
_ASSET_SUB_CATEGORIES = [
    # Cash
    ("cash", "cash",             "Cash",              10),
    ("cash", "money_market",     "Money Market",      20),
    ("cash", "checking_account", "Checking Account",  30),
    ("cash", "savings_account",  "Savings Account",   40),
    ("cash", "cds",              "CDs",               50),
    ("cash", "t_bills",          "T-Bills",           60),
    # Fixed Income
    ("fixed_income", "gov_agencies",         "Gov & Agencies",                10),
    ("fixed_income", "municipals",           "Municipals",                    20),
    ("fixed_income", "investment_grade",     "Investment Grade",              30),
    ("fixed_income", "high_yield",           "High Yield",                    40),
    ("fixed_income", "emerging_markets",     "Emerging Markets",              50),
    ("fixed_income", "preferred_shares",     "Preferred Shares",              60),
    ("fixed_income", "perpetual_preferred",  "Perpetual Preferred",           70),
    ("fixed_income", "structured_fxd_inc",   "Structured Products (Fxd Inc)", 80),
    ("fixed_income", "fxd_inc_other",        "Other (ETF, Funds, etc.)",      90),
    # Equity
    ("equity", "us_equities_stocks",     "US Equities (Stocks)",            10),
    ("equity", "us_equities_funds",      "US Equities (Funds)",             20),
    ("equity", "equities_etfs",          "Equities (ETFs)",                 30),
    ("equity", "global_equities_etfs",   "Global Equities (ETFs, Stocks)",  40),
    ("equity", "global_equities_funds",  "Global Equities (Funds)",         50),
    ("equity", "emerging_markets",       "Emerging Markets",                60),
    ("equity", "structured_equities",    "Structured Products (Equities)",  70),
    ("equity", "mlps",                   "MLPs",                            80),
    ("equity", "private_equity",         "Private Equity",                  90),
    ("equity", "equity_other",           "Other (Options, etc.)",          100),
    # Alternative
    ("alternative", "multi_strategy",   "Multi Strategy",   10),
    ("alternative", "long_short",       "Long / Short",     20),
    ("alternative", "global_macro_fx",  "Global Macro & FX", 30),
    ("alternative", "event_driven",     "Event Driven",     40),
    ("alternative", "arbitrage",        "Arbitrage",        50),
    ("alternative", "distressed",       "Distressed",       60),
    ("alternative", "relative_value",   "Relative Value",   70),
    ("alternative", "alt_other",        "Other",            80),
    # Currencies / Crypto
    ("currencies_crypto", "eur_cad", "EUR, CAD",                          10),
    ("currencies_crypto", "gbp",     "GBP",                               20),
    ("currencies_crypto", "crypto",  "Crypto (Bitcoin, Ethereum, etc.)",  30),
    # Commodities — placeholder
    ("commodities", "commodities_other", "Other", 10),
    # Real Estate — placeholder
    ("real_estate", "real_estate_other", "Other", 10),
]


def upgrade() -> None:
    bind = op.get_bind()

    for slug, display in _FAMILY_BRANCHES:
        bind.execute(
            text(
                "INSERT INTO family_branches (slug, display_name) "
                "VALUES (:slug, :display) "
                "ON CONFLICT (slug) DO NOTHING"
            ),
            {"slug": slug, "display": display},
        )

    for full_name, surname, role, branch_slug, is_approver in _PRINCIPALS:
        bind.execute(
            text(
                "INSERT INTO principals (full_name, surname_at_birth, role, branch_id, is_approver) "
                "SELECT :full_name, :surname, :role, fb.id, :is_approver "
                "FROM family_branches fb WHERE fb.slug = :branch_slug "
                "ON CONFLICT DO NOTHING"
            ),
            {
                "full_name": full_name,
                "surname": surname,
                "role": role,
                "branch_slug": branch_slug,
                "is_approver": is_approver,
            },
        )

    for slug, display in _VEHICLE_TYPES:
        bind.execute(
            text(
                "INSERT INTO vehicle_types (slug, display_name) "
                "VALUES (:slug, :display) "
                "ON CONFLICT (slug) DO NOTHING"
            ),
            {"slug": slug, "display": display},
        )

    for slug, display, sort_order in _ASSET_CLASSES:
        bind.execute(
            text(
                "INSERT INTO asset_classes (slug, display_name, sort_order) "
                "VALUES (:slug, :display, :sort_order) "
                "ON CONFLICT (slug) DO NOTHING"
            ),
            {"slug": slug, "display": display, "sort_order": sort_order},
        )

    for parent_slug, slug, display, sort_order in _ASSET_SUB_CATEGORIES:
        bind.execute(
            text(
                "INSERT INTO asset_sub_categories (asset_class_id, slug, display_name, sort_order) "
                "SELECT ac.id, :slug, :display, :sort_order "
                "FROM asset_classes ac WHERE ac.slug = :parent_slug "
                "ON CONFLICT (asset_class_id, slug) DO NOTHING"
            ),
            {
                "parent_slug": parent_slug,
                "slug": slug,
                "display": display,
                "sort_order": sort_order,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()

    sub_slugs = [t[1] for t in _ASSET_SUB_CATEGORIES]
    class_slugs = [t[0] for t in _ASSET_CLASSES]
    vehicle_type_slugs = [t[0] for t in _VEHICLE_TYPES]
    principal_names = [t[0] for t in _PRINCIPALS]
    branch_slugs = [t[0] for t in _FAMILY_BRANCHES]

    bind.execute(text("DELETE FROM asset_sub_categories WHERE slug = ANY(:s)"), {"s": sub_slugs})
    bind.execute(text("DELETE FROM asset_classes WHERE slug = ANY(:s)"), {"s": class_slugs})
    bind.execute(text("DELETE FROM vehicle_types WHERE slug = ANY(:s)"), {"s": vehicle_type_slugs})
    bind.execute(text("DELETE FROM principals WHERE full_name = ANY(:s)"), {"s": principal_names})
    bind.execute(text("DELETE FROM family_branches WHERE slug = ANY(:s)"), {"s": branch_slugs})
