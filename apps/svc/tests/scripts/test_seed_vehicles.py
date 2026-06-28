"""Tests for the seed_vehicles validation paths (no DB required)."""

from __future__ import annotations

import pytest

# Module imports trigger secrets.load_secrets_into_env() at import time; with
# USE_SECRET_MANAGER=false (default in base_env / conftest) that's a no-op.
from scripts.seed_vehicles import (
    _NULL_FAMILY_BRANCH_ALIASES,
    SeedError,
    _validate_owner_references,
    _validate_vehicle,
)


def _v(**overrides) -> dict:
    base = {
        "legal_name": "Sample Trust",
        "short_name": "SAMPLE",
        "vehicle_type": "irrevocable_trust",
        "ownerships": [
            {
                "principal": "Jane Doe",
                "role": "trustee",
                "effective_from": "2020-01-01",
            }
        ],
    }
    base.update(overrides)
    return base


def test_valid_vehicle_passes():
    _validate_vehicle(_v(), 0)  # no raise


def test_invalid_vehicle_type_rejected():
    with pytest.raises(SeedError, match="invalid vehicle_type"):
        _validate_vehicle(_v(vehicle_type="trust"), 0)


def test_invalid_role_rejected():
    bad = _v(
        ownerships=[
            {"principal": "X", "role": "beneficiary", "effective_from": "2020-01-01"}
        ]
    )
    with pytest.raises(SeedError, match="invalid role"):
        _validate_vehicle(bad, 0)


def test_missing_required_field_rejected():
    bad = _v()
    del bad["short_name"]
    with pytest.raises(SeedError, match="short_name"):
        _validate_vehicle(bad, 0)


def test_empty_ownerships_rejected():
    with pytest.raises(SeedError, match="non-empty"):
        _validate_vehicle(_v(ownerships=[]), 0)


@pytest.mark.parametrize("alias", sorted(_NULL_FAMILY_BRANCH_ALIASES))
def test_shared_family_branch_aliases_accepted(alias: str):
    _validate_vehicle(_v(family_branch=alias), 0)


def test_explicit_family_branch_accepted():
    _validate_vehicle(_v(family_branch="sternberg_roth"), 0)
    _validate_vehicle(_v(family_branch="sternberg_pardo"), 0)


def test_invalid_family_branch_rejected():
    with pytest.raises(SeedError, match="invalid family_branch"):
        _validate_vehicle(_v(family_branch="unknown_branch"), 0)


def test_self_referential_ownership_rejected():
    entries = [
        _v(
            short_name="SFT",
            ownerships=[
                {"principal": "SFT", "role": "owner", "effective_from": "2020-01-01"},
            ],
        )
    ]
    with pytest.raises(SeedError, match="references itself"):
        _validate_owner_references(entries)


def test_owner_references_pass_for_clean_entries():
    entries = [
        _v(short_name="A"),
        _v(
            short_name="B",
            ownerships=[
                # References A by short_name — vehicle-as-owner. Pre-pass
                # doesn't validate this; DB lookup at upsert time handles it.
                {"principal": "A", "role": "member", "effective_from": "2020-01-01"},
            ],
        ),
    ]
    _validate_owner_references(entries)  # no raise
