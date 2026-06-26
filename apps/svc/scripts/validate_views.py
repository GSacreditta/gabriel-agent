"""Day-6: validate the three reporting views.

Reads `v_smfo_aggregate`, `v_per_vehicle`, `v_per_family` and prints their
contents. With --with-fixtures, inserts a small synthetic dataset (two
investments, positions across a few vehicles) inside a single transaction
and ROLLS BACK at the end, so the DB is unchanged.

Use this after seeding vehicles to confirm:
1. View C correctly attributes vehicle-tagged-with-family investments.
2. View C correctly EXCLUDES shared vehicles (e.g., SM18 LLC, 7Stern) that
   have family_branch_id = NULL.
3. View B per-vehicle returns one row per (vehicle, investment) position.
4. View A SMFO aggregate sums everything regardless of family tag.

Usage:
    cd apps/svc
    python -m scripts.validate_views                  # read-only: dump current views
    python -m scripts.validate_views --with-fixtures  # add test data, dump, roll back
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from typing import Iterable

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from app.core import secrets

secrets.load_secrets_into_env()

from app.core.config import get_settings  # noqa: E402


def _build_sync_engine() -> Engine:
    s = get_settings()
    sync_url = s.database_url.replace("+asyncpg", "+psycopg2")
    return create_engine(sync_url, future=True)


def _dump_rows(label: str, rows: Iterable, headers: list[str]) -> None:
    print(f"\n=== {label} ===")
    rows = list(rows)
    if not rows:
        print("  (empty)")
        return
    widths = [max(len(h), max(len(str(r[i])) for r in rows)) for i, h in enumerate(headers)]
    print("  " + "  ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("  " + "  ".join("-" * w for w in widths))
    for r in rows:
        print("  " + "  ".join(str(r[i]).ljust(w) for i, w in enumerate(widths)))


def _query_views(conn: Connection) -> None:
    a = conn.execute(
        text(
            """
            SELECT asset_class, liquidity_type, sub_category,
                   total_value, total_commitment, total_funded, investment_count
            FROM v_smfo_aggregate
            ORDER BY asset_class, liquidity_type
            """
        )
    ).fetchall()
    _dump_rows(
        "v_smfo_aggregate",
        a,
        ["asset_class", "liquidity", "sub_cat", "value", "commit", "funded", "n"],
    )

    b = conn.execute(
        text(
            """
            SELECT vehicle, investment, asset_class, liquidity_type,
                   commitment_amount, funded_amount, current_value, structure
            FROM v_per_vehicle
            ORDER BY vehicle, investment
            """
        )
    ).fetchall()
    _dump_rows(
        "v_per_vehicle",
        b,
        ["vehicle", "investment", "asset_class", "liq", "commit", "funded", "value", "struct"],
    )

    c = conn.execute(
        text(
            """
            SELECT branch, asset_class, attributed_value,
                   attributed_commitment, investment_count
            FROM v_per_family
            ORDER BY branch, asset_class
            """
        )
    ).fetchall()
    _dump_rows(
        "v_per_family",
        c,
        ["branch", "asset_class", "att_value", "att_commit", "n"],
    )


def _insert_fixtures(conn: Connection) -> None:
    """Insert synthetic data so the views have something to render.

    Assumes vehicles have been seeded via scripts/seed_vehicles. Uses the
    short_names from config/vehicles.yaml. If any of these vehicles is
    missing, the inserts skip silently.
    """
    asset_class_row = conn.execute(
        text("SELECT id FROM asset_classes WHERE slug = 'equity'")
    ).fetchone()
    sub_cat_row = conn.execute(
        text("SELECT id FROM asset_sub_categories WHERE slug = 'private_equity'")
    ).fetchone()
    if not asset_class_row or not sub_cat_row:
        print("WARN: equity / private_equity reference data missing; skipping fixtures")
        return

    asset_class_id = asset_class_row[0]
    sub_cat_id = sub_cat_row[0]

    # Two test investments
    inv1 = conn.execute(
        text(
            """
            INSERT INTO investments (name, issuer, asset_class_id, sub_category_id,
                                     liquidity_type, status)
            VALUES ('TEST: Acme PE Fund IV', 'Acme Capital', :ac, :sc,
                    'illiquid', 'active')
            RETURNING id
            """
        ),
        {"ac": asset_class_id, "sc": sub_cat_id},
    ).fetchone()[0]

    inv2 = conn.execute(
        text(
            """
            INSERT INTO investments (name, issuer, asset_class_id,
                                     liquidity_type, status)
            VALUES ('TEST: Public Equities Sleeve', 'Mixed', :ac,
                    'liquid', 'active')
            RETURNING id
            """
        ),
        {"ac": asset_class_id},
    ).fetchone()[0]

    # Look up vehicles by short_name (skip if missing)
    def _vid(short: str) -> str | None:
        row = conn.execute(
            text("SELECT id FROM vehicles WHERE short_name = :s"), {"s": short}
        ).fetchone()
        return str(row[0]) if row else None

    positions = [
        # inv1: TEST PE Fund IV — held parallel across GS_Personal + DS_Personal
        (inv1, "GS_Personal", "parallel_commitment", 250_000, 100_000, 130_000, 100),
        (inv1, "DS_Personal", "parallel_commitment", 250_000, 100_000, 130_000, 100),
        # inv2: Public Equities — shared SM18 LLC (NOT family-tagged) + G&G Trust
        (inv2, "SM18 LLC",    "shared_llc_internal", 500_000, 500_000, 575_000, 100),
        (inv2, "G&G IRR Trust", "parallel_commitment", 200_000, 200_000, 230_000, 100),
    ]

    for inv_id, short, structure, commit, funded, value, pct in positions:
        vid = _vid(short)
        if not vid:
            print(f"WARN: vehicle '{short}' not found; skipping position")
            continue
        conn.execute(
            text(
                """
                INSERT INTO investment_positions
                  (investment_id, vehicle_id, structure, commitment_amount,
                   funded_amount, current_value, ownership_pct, effective_from)
                VALUES
                  (:inv, :vid, :structure, :commit, :funded, :value, :pct, :ef)
                """
            ),
            {
                "inv": inv_id,
                "vid": vid,
                "structure": structure,
                "commit": commit,
                "funded": funded,
                "value": value,
                "pct": pct,
                "ef": date(2024, 1, 1),
            },
        )

    print("INFO: fixtures inserted (will be rolled back)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the 3 reporting views")
    parser.add_argument(
        "--with-fixtures",
        action="store_true",
        help="Insert synthetic test positions before dumping (rolled back at end).",
    )
    args = parser.parse_args()

    engine = _build_sync_engine()

    if args.with_fixtures:
        # Single transaction; explicit rollback at the end leaves DB unchanged.
        with engine.connect() as conn:
            trans = conn.begin()
            try:
                _insert_fixtures(conn)
                _query_views(conn)
            finally:
                trans.rollback()
                print("\nINFO: transaction rolled back, DB unchanged")
    else:
        with engine.connect() as conn:
            _query_views(conn)

    return 0


if __name__ == "__main__":
    sys.exit(main())
