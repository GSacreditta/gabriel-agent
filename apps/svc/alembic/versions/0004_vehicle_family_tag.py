"""vehicle-level family tag; drop beneficiary attribution

Revision ID: 0004_vehicle_family_tag
Revises: 0003_vehicle_owns_vehicle
Create Date: 2026-06-24

User clarification: the platform is NOT for estate planning. Trusts are
autonomous vehicles for reporting purposes — there is no beneficiary
flow-through. All transactions and reporting refer to the vehicle name.

This migration replaces the recursive ownership-chain view C with a flat
vehicle-level family tag:

- Each vehicle MAY be tagged with a family branch (sternberg_roth or
  sternberg_pardo). NULL means "shared / umbrella" (SM18 LLC, 7Stern) —
  excluded from per-family view, still counted in SMFO aggregate.
- v_per_family becomes a simple JOIN on vehicles.family_branch_id.
- The vehicle_owner_id column on vehicle_ownerships stays — recording
  which trusts own a slice of an LLC is still legitimate, even though it
  no longer drives recursive family attribution.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0004_vehicle_family_tag"
down_revision: Union[str, None] = "0003_vehicle_owns_vehicle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add the tag column.
    op.add_column(
        "vehicles",
        sa.Column(
            "family_branch_id",
            UUID(as_uuid=True),
            sa.ForeignKey("family_branches.id"),
            nullable=True,
        ),
    )

    # 2. Replace v_per_family with a flat JOIN — no recursion, no
    #    beneficiary inference. A vehicle either has a family tag or it
    #    doesn't (shared vehicles drop out of per-family view by design).
    op.execute("DROP VIEW IF EXISTS v_per_family")
    op.execute(
        """
        CREATE VIEW v_per_family AS
        SELECT
            fb.slug         AS branch,
            ac.display_name AS asset_class,
            SUM(ip.current_value)     AS attributed_value,
            SUM(ip.commitment_amount) AS attributed_commitment,
            COUNT(DISTINCT i.id)      AS investment_count
        FROM family_branches fb
        JOIN vehicles v             ON v.family_branch_id = fb.id
        JOIN investment_positions ip ON ip.vehicle_id = v.id
                                     AND ip.effective_to IS NULL
        JOIN investments i          ON i.id = ip.investment_id
                                     AND i.status = 'active'
        JOIN asset_classes ac       ON ac.id = i.asset_class_id
        GROUP BY fb.slug, ac.display_name;
        """
    )


def downgrade() -> None:
    # Restore the recursive form from 0003.
    op.execute("DROP VIEW IF EXISTS v_per_family")
    op.execute(
        """
        CREATE VIEW v_per_family AS
        WITH RECURSIVE
        vehicle_to_principal AS (
            SELECT vo.vehicle_id, vo.principal_id, COALESCE(vo.ownership_pct, 0) AS pct
            FROM vehicle_ownerships vo
            WHERE vo.principal_id IS NOT NULL
              AND vo.effective_to IS NULL
              AND vo.ownership_pct IS NOT NULL
        ),
        vehicle_to_vehicle AS (
            SELECT vo.vehicle_id AS holder_id, vo.vehicle_owner_id AS owner_id,
                   COALESCE(vo.ownership_pct, 0) AS pct
            FROM vehicle_ownerships vo
            WHERE vo.vehicle_owner_id IS NOT NULL
              AND vo.effective_to IS NULL
              AND vo.ownership_pct IS NOT NULL
        ),
        -- `path` carries visited vehicles so we don't walk back into a cycle.
        attribution(vehicle_id, principal_id, weight, path) AS (
            SELECT vehicle_id, principal_id, pct / 100.0, ARRAY[vehicle_id]
            FROM vehicle_to_principal
            UNION ALL
            SELECT vv.holder_id, a.principal_id, a.weight * vv.pct / 100.0,
                   a.path || vv.holder_id
            FROM vehicle_to_vehicle vv
            JOIN attribution a ON a.vehicle_id = vv.owner_id
            WHERE NOT (vv.holder_id = ANY(a.path))
        )
        SELECT
            fb.slug         AS branch,
            ac.display_name AS asset_class,
            SUM(ip.current_value     * a.weight) AS attributed_value,
            SUM(ip.commitment_amount * a.weight) AS attributed_commitment
        FROM family_branches fb
        JOIN principals p          ON p.branch_id = fb.id AND p.is_approver = true
        JOIN attribution a         ON a.principal_id = p.id
        JOIN investment_positions ip ON ip.vehicle_id = a.vehicle_id
                                     AND ip.effective_to IS NULL
        JOIN investments i         ON i.id = ip.investment_id AND i.status = 'active'
        JOIN asset_classes ac      ON ac.id = i.asset_class_id
        GROUP BY fb.slug, ac.display_name;
        """
    )

    op.drop_column("vehicles", "family_branch_id")
