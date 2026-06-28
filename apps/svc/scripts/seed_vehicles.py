"""Day-5 seed: load vehicles + vehicle_ownerships from config/vehicles.yaml.

Idempotent. Re-running upserts by `short_name` for vehicles and by the partial
unique indexes on `vehicle_ownerships` (principal-based and vehicle-based).

Usage (from repo root, after running alembic migrations):

    python -m scripts.seed_vehicles                       # default config path
    python -m scripts.seed_vehicles --config /path/to.yaml
    python -m scripts.seed_vehicles --dry-run             # validate only, no writes

Run with the working directory set to apps/svc/ so `app` resolves:

    cd apps/svc
    python -m scripts.seed_vehicles
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core import secrets

secrets.load_secrets_into_env()

from app.core.config import get_settings  # noqa: E402

# Constraints — mirror the seed migration + plan.
_VALID_VEHICLE_TYPES = {"irrevocable_trust", "llc", "personal_account", "operational_llc"}
_VALID_ROLES = {"trustee", "manager", "member", "owner"}
_VALID_FAMILY_BRANCHES = {"sternberg_roth", "sternberg_pardo"}
# Aliases that mean "no family attribution" (umbrella / shared vehicle).
# Stored as NULL in vehicles.family_branch_id; absent from view C.
_NULL_FAMILY_BRANCH_ALIASES = {"shared", "umbrella", "smfo", "none"}
_DEFAULT_CONFIG = Path(__file__).resolve().parents[3] / "config" / "vehicles.yaml"


class SeedError(Exception):
    """Validation failure surfaced to the operator."""


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_vehicle(entry: dict, idx: int) -> None:
    for field in ("legal_name", "short_name", "vehicle_type", "ownerships"):
        if field not in entry:
            raise SeedError(f"vehicle #{idx}: missing required field '{field}'")

    if entry["vehicle_type"] not in _VALID_VEHICLE_TYPES:
        raise SeedError(
            f"vehicle '{entry['short_name']}': invalid vehicle_type "
            f"'{entry['vehicle_type']}' (allowed: {sorted(_VALID_VEHICLE_TYPES)})"
        )

    fb = entry.get("family_branch")
    if fb is not None and fb not in _VALID_FAMILY_BRANCHES and fb not in _NULL_FAMILY_BRANCH_ALIASES:
        raise SeedError(
            f"vehicle '{entry['short_name']}': invalid family_branch '{fb}' "
            f"(allowed: {sorted(_VALID_FAMILY_BRANCHES)}, "
            f"or one of {sorted(_NULL_FAMILY_BRANCH_ALIASES)} / null / omit for shared)"
        )

    if not isinstance(entry["ownerships"], list) or not entry["ownerships"]:
        raise SeedError(f"vehicle '{entry['short_name']}': ownerships must be a non-empty list")

    for j, own in enumerate(entry["ownerships"]):
        for field in ("principal", "role", "effective_from"):
            if field not in own:
                raise SeedError(
                    f"vehicle '{entry['short_name']}' ownership #{j}: missing '{field}'"
                )
        if own["role"] not in _VALID_ROLES:
            raise SeedError(
                f"vehicle '{entry['short_name']}' ownership #{j}: invalid role "
                f"'{own['role']}' (allowed: {sorted(_VALID_ROLES)})"
            )


# ---------------------------------------------------------------------------
# Reference data lookup helpers
# ---------------------------------------------------------------------------


def _lookup_id(engine: Engine, sql: str, **params: Any) -> str | None:
    with engine.connect() as conn:
        row = conn.execute(text(sql), params).fetchone()
        return str(row[0]) if row else None


def _resolve_vehicle_type_id(engine: Engine, slug: str) -> str:
    rid = _lookup_id(engine, "SELECT id FROM vehicle_types WHERE slug = :slug", slug=slug)
    if not rid:
        raise SeedError(f"vehicle_type slug '{slug}' not found in DB (run migrations first?)")
    return rid


def _resolve_family_branch_id(engine: Engine, slug: str | None) -> str | None:
    if slug is None or slug in _NULL_FAMILY_BRANCH_ALIASES:
        return None
    rid = _lookup_id(engine, "SELECT id FROM family_branches WHERE slug = :slug", slug=slug)
    if not rid:
        raise SeedError(f"family_branch slug '{slug}' not found in DB")
    return rid


def _resolve_principal_id(engine: Engine, full_name: str) -> str | None:
    return _lookup_id(
        engine,
        "SELECT id FROM principals WHERE full_name = :n",
        n=full_name,
    )


def _resolve_vehicle_id_by_short(engine: Engine, short_name: str) -> str | None:
    return _lookup_id(
        engine,
        "SELECT id FROM vehicles WHERE short_name = :s",
        s=short_name,
    )


# ---------------------------------------------------------------------------
# Upserts
# ---------------------------------------------------------------------------


def _upsert_vehicle(engine: Engine, entry: dict) -> str:
    """Insert if not present (by short_name), else update mutable fields. Return id."""
    vt_id = _resolve_vehicle_type_id(engine, entry["vehicle_type"])
    fb_id = _resolve_family_branch_id(engine, entry.get("family_branch"))

    formed_on = entry.get("formed_on")
    if isinstance(formed_on, str):
        formed_on = date.fromisoformat(formed_on)

    params = {
        "legal_name": entry["legal_name"],
        "short_name": entry["short_name"],
        "vehicle_type_id": vt_id,
        "family_branch_id": fb_id,
        "tax_id": entry.get("tax_id"),
        "jurisdiction": entry.get("jurisdiction"),
        "formed_on": formed_on,
        "drive_folder_id": entry.get("drive_folder_id"),
        "notes": entry.get("notes"),
    }

    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT id FROM vehicles WHERE short_name = :short_name"),
            {"short_name": entry["short_name"]},
        ).fetchone()

        if existing:
            conn.execute(
                text(
                    """
                    UPDATE vehicles SET
                      legal_name = :legal_name,
                      vehicle_type_id = :vehicle_type_id,
                      family_branch_id = :family_branch_id,
                      tax_id = :tax_id,
                      jurisdiction = :jurisdiction,
                      formed_on = :formed_on,
                      drive_folder_id = :drive_folder_id,
                      notes = :notes,
                      updated_at = now()
                    WHERE short_name = :short_name
                    """
                ),
                params,
            )
            return str(existing[0])

        row = conn.execute(
            text(
                """
                INSERT INTO vehicles
                  (legal_name, short_name, vehicle_type_id, family_branch_id,
                   tax_id, jurisdiction, formed_on, drive_folder_id, notes)
                VALUES
                  (:legal_name, :short_name, :vehicle_type_id, :family_branch_id,
                   :tax_id, :jurisdiction, :formed_on, :drive_folder_id, :notes)
                RETURNING id
                """
            ),
            params,
        ).fetchone()
        return str(row[0])


def _upsert_ownership(engine: Engine, vehicle_id: str, own: dict, vehicle_short: str) -> str:
    """Insert ownership row if not already present.

    Owner side: principal name first; if it doesn't resolve to a principal,
    look up by vehicle short_name (a trust-as-member-of-LLC case).
    """
    principal_full = own["principal"]
    principal_id = _resolve_principal_id(engine, principal_full)
    vehicle_owner_id = None
    if not principal_id:
        vehicle_owner_id = _resolve_vehicle_id_by_short(engine, principal_full)
        if not vehicle_owner_id:
            raise SeedError(
                f"vehicle '{vehicle_short}': owner '{principal_full}' did not match any "
                f"principal full_name or vehicle short_name"
            )
        if vehicle_owner_id == vehicle_id:
            raise SeedError(
                f"vehicle '{vehicle_short}': a vehicle cannot own itself"
            )

    effective_from = own["effective_from"]
    if isinstance(effective_from, str):
        effective_from = date.fromisoformat(effective_from)
    effective_to = own.get("effective_to")
    if isinstance(effective_to, str):
        effective_to = date.fromisoformat(effective_to)

    params = {
        "vehicle_id": vehicle_id,
        "principal_id": principal_id,
        "vehicle_owner_id": vehicle_owner_id,
        "role": own["role"],
        "ownership_pct": own.get("ownership_pct"),
        "effective_from": effective_from,
        "effective_to": effective_to,
    }

    with engine.begin() as conn:
        # Check for an existing matching row (partial unique indexes give us
        # at most one match per (vehicle, owner, role, effective_from)).
        if principal_id:
            existing = conn.execute(
                text(
                    """
                    SELECT id FROM vehicle_ownerships
                    WHERE vehicle_id = :vehicle_id
                      AND principal_id = :principal_id
                      AND role = :role
                      AND effective_from = :effective_from
                    """
                ),
                params,
            ).fetchone()
        else:
            existing = conn.execute(
                text(
                    """
                    SELECT id FROM vehicle_ownerships
                    WHERE vehicle_id = :vehicle_id
                      AND vehicle_owner_id = :vehicle_owner_id
                      AND role = :role
                      AND effective_from = :effective_from
                    """
                ),
                params,
            ).fetchone()

        if existing:
            conn.execute(
                text(
                    """
                    UPDATE vehicle_ownerships SET
                      ownership_pct = :ownership_pct,
                      effective_to = :effective_to,
                      updated_at = now()
                    WHERE id = :id
                    """
                ),
                {"id": existing[0], **params},
            )
            return str(existing[0])

        row = conn.execute(
            text(
                """
                INSERT INTO vehicle_ownerships
                  (vehicle_id, principal_id, vehicle_owner_id, role,
                   ownership_pct, effective_from, effective_to)
                VALUES
                  (:vehicle_id, :principal_id, :vehicle_owner_id, :role,
                   :ownership_pct, :effective_from, :effective_to)
                RETURNING id
                """
            ),
            params,
        ).fetchone()
        return str(row[0])


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def _build_sync_engine() -> Engine:
    """Alembic uses psycopg2 too — same swap."""
    s = get_settings()
    sync_url = s.database_url.replace("+asyncpg", "+psycopg2")
    return create_engine(sync_url, future=True)


def _validate_owner_references(entries: list[dict]) -> None:
    """Detect self-referential ownerships before any DB writes.

    Full validation of owner references (does this principal full_name exist?
    does this short_name resolve to a vehicle?) happens at upsert time against
    the DB — see _upsert_ownership. This pre-pass only catches the unambiguous
    self-reference case where a vehicle lists itself as one of its owners.
    """
    for entry in entries:
        for own in entry["ownerships"]:
            if own["principal"] == entry["short_name"]:
                raise SeedError(
                    f"vehicle '{entry['short_name']}' references itself in ownerships"
                )


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed vehicles + ownerships from YAML")
    parser.add_argument(
        "--config",
        type=Path,
        default=_DEFAULT_CONFIG,
        help=f"Path to vehicles.yaml (default: {_DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the YAML and DB references; do not write.",
    )
    args = parser.parse_args()

    if not args.config.exists():
        print(f"ERROR: config not found: {args.config}", file=sys.stderr)
        return 2

    with args.config.open(encoding="utf-8") as f:
        doc = yaml.safe_load(f)

    if not isinstance(doc, dict) or "vehicles" not in doc:
        print("ERROR: top-level YAML must have a 'vehicles:' list", file=sys.stderr)
        return 2

    entries = doc["vehicles"]
    if not isinstance(entries, list) or not entries:
        print("ERROR: 'vehicles' must be a non-empty list", file=sys.stderr)
        return 2

    try:
        for i, entry in enumerate(entries):
            _validate_vehicle(entry, i)
        _validate_owner_references(entries)
    except SeedError as exc:
        print(f"VALIDATION ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"YAML valid: {len(entries)} vehicle(s)")

    if args.dry_run:
        print("--dry-run: not writing to DB")
        return 0

    engine = _build_sync_engine()

    # Two passes: vehicles first (so vehicle-as-owner lookups can resolve),
    # then ownerships once all vehicle IDs exist.
    vehicle_ids: dict[str, str] = {}
    for entry in entries:
        vid = _upsert_vehicle(engine, entry)
        vehicle_ids[entry["short_name"]] = vid
        print(f"  vehicle  upsert  {entry['short_name']:<20}  {vid}")

    for entry in entries:
        vid = vehicle_ids[entry["short_name"]]
        for own in entry["ownerships"]:
            try:
                oid = _upsert_ownership(engine, vid, own, entry["short_name"])
            except SeedError as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                return 3
            print(
                f"  owner    upsert  {entry['short_name']:<20}  "
                f"{own['principal']:<25}  {own['role']:<10}  {oid}"
            )

    print(f"\nDone. {len(entries)} vehicle(s), "
          f"{sum(len(e['ownerships']) for e in entries)} ownership(s) processed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
