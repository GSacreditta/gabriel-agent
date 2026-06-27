"""vehicle-owns-vehicle support

Revision ID: 0003_vehicle_owns_vehicle
Revises: 0002_seed_reference
Create Date: 2026-06-24

Real-world data surfaced a gap: irrevocable trusts can be members of
operating LLCs. Example: Seven Stern LLC (7Stern) has D&V IRR Trust and
G&G IRR Trust as 25% members. The initial schema modeled ownership only
as principal→vehicle; this migration generalises to allow either a
principal OR another vehicle as the owner side.

Schema changes:
- vehicle_ownerships.principal_id becomes nullable.
- New column vehicle_ownerships.vehicle_owner_id (FK -> vehicles.id), nullable.
- XOR check constraint: exactly one of the two FKs is set per row.
- No-self-ownership check constraint.
- Replace the legacy unique constraint with two partial unique indexes,
  one per owner kind, so PG-correctly enforces dedup despite the XOR nulls.

View change:
- v_per_family is rebuilt as a recursive CTE so that a vehicle owned by
  another vehicle resolves transitively until it lands on a principal
  with a family branch. Trust beneficiary ownerships are required for
  this to actually attribute trust slices to a family — without them,
  the trust portion drops out of view C silently. Document this caveat.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0003_vehicle_owns_vehicle"
down_revision: Union[str, None] = "0002_seed_reference"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add new column.
    op.add_column(
        "vehicle_ownerships",
        sa.Column(
            "vehicle_owner_id",
            UUID(as_uuid=True),
            sa.ForeignKey("vehicles.id"),
            nullable=True,
        ),
    )

    # 2. Relax principal_id to nullable.
    op.alter_column(
        "vehicle_ownerships",
        "principal_id",
        existing_type=UUID(as_uuid=True),
        nullable=True,
    )

    # 3. Drop legacy unique constraint, replace with partial uniques.
    op.drop_constraint(
        "uq_vehicle_ownerships", "vehicle_ownerships", type_="unique"
    )
    op.create_index(
        "uq_vehicle_ownerships_by_principal",
        "vehicle_ownerships",
        ["vehicle_id", "principal_id", "role", "effective_from"],
        unique=True,
        postgresql_where=sa.text("principal_id IS NOT NULL"),
    )
    op.create_index(
        "uq_vehicle_ownerships_by_vehicle",
        "vehicle_ownerships",
        ["vehicle_id", "vehicle_owner_id", "role", "effective_from"],
        unique=True,
        postgresql_where=sa.text("vehicle_owner_id IS NOT NULL"),
    )

    # 4. XOR + no-self-ownership check constraints.
    op.create_check_constraint(
        "ck_vehicle_ownerships_owner_xor",
        "vehicle_ownerships",
        "(principal_id IS NOT NULL)::int + (vehicle_owner_id IS NOT NULL)::int = 1",
    )
    op.create_check_constraint(
        "ck_vehicle_ownerships_no_self_own",
        "vehicle_ownerships",
        "vehicle_owner_id IS NULL OR vehicle_owner_id <> vehicle_id",
    )

    # 5. Rebuild v_per_family with a recursive CTE that walks vehicle→vehicle
    #    edges down to principals, then attributes via the principal's family
    #    branch. A trust whose only ownerships are trustees (no beneficiaries
    #    with ownership_pct) contributes 0 to attributed_value — by design,
    #    since trustees have no economic interest.
    op.execute("DROP VIEW IF EXISTS v_per_family")
    op.execute(
        """
        CREATE VIEW v_per_family AS
        WITH RECURSIVE
        -- Direct vehicle→principal ownership (economic, not trustee/manager).
        vehicle_to_principal AS (
            SELECT
                vo.vehicle_id,
                vo.principal_id,
                COALESCE(vo.ownership_pct, 0) AS pct
            FROM vehicle_ownerships vo
            WHERE vo.principal_id IS NOT NULL
              AND vo.effective_to IS NULL
              AND vo.ownership_pct IS NOT NULL
        ),
        -- Vehicle→vehicle ownership edges.
        vehicle_to_vehicle AS (
            SELECT
                vo.vehicle_id           AS holder_id,    -- the vehicle that has the slice
                vo.vehicle_owner_id     AS owner_id,     -- the vehicle that owns the slice
                COALESCE(vo.ownership_pct, 0) AS pct
            FROM vehicle_ownerships vo
            WHERE vo.vehicle_owner_id IS NOT NULL
              AND vo.effective_to IS NULL
              AND vo.ownership_pct IS NOT NULL
        ),
        -- Walk the chain: every vehicle gets attributed to (principal, weight)
        -- pairs, where weight is the product of percentages along the path.
        -- `path` carries the set of visited vehicles so we can refuse to walk
        -- back into one. The CHECK constraint only prevents direct
        -- self-ownership; multi-hop cycles would otherwise loop until the
        -- planner exhausts work_mem. This guard makes the view DoS-safe.
        attribution(vehicle_id, principal_id, weight, path) AS (
            -- Base case: direct principal ownership of this vehicle.
            SELECT vehicle_id, principal_id, pct / 100.0, ARRAY[vehicle_id]
            FROM vehicle_to_principal

            UNION ALL

            -- Recursive case: vehicle V is owned (pct%) by vehicle V', and V'
            -- is in turn attributed to some principal at weight W. So V flows
            -- to that principal at W * pct/100.
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


def downgrade() -> None:
    # 1. Revert v_per_family to the non-recursive form from 0001.
    op.execute("DROP VIEW IF EXISTS v_per_family")
    op.execute(
        """
        CREATE VIEW v_per_family AS
        SELECT
          fb.slug         AS branch,
          ac.display_name AS asset_class,
          SUM(ip.current_value * COALESCE(vo.ownership_pct, 100) / 100.0)     AS attributed_value,
          SUM(ip.commitment_amount * COALESCE(vo.ownership_pct, 100) / 100.0) AS attributed_commitment
        FROM family_branches fb
        JOIN principals p ON p.branch_id = fb.id AND p.is_approver = true
        JOIN vehicle_ownerships vo ON vo.principal_id = p.id AND vo.effective_to IS NULL
        JOIN vehicles v ON v.id = vo.vehicle_id
        JOIN investment_positions ip ON ip.vehicle_id = v.id AND ip.effective_to IS NULL
        JOIN investments i ON i.id = ip.investment_id
        JOIN asset_classes ac ON ac.id = i.asset_class_id
        WHERE i.status = 'active'
        GROUP BY fb.slug, ac.display_name;
        """
    )

    # 2. Drop check constraints + partial indexes.
    op.drop_constraint(
        "ck_vehicle_ownerships_no_self_own", "vehicle_ownerships", type_="check"
    )
    op.drop_constraint(
        "ck_vehicle_ownerships_owner_xor", "vehicle_ownerships", type_="check"
    )
    op.drop_index("uq_vehicle_ownerships_by_vehicle", table_name="vehicle_ownerships")
    op.drop_index("uq_vehicle_ownerships_by_principal", table_name="vehicle_ownerships")

    # 3. Restore the legacy unique constraint (requires no rows with NULL principal_id).
    op.create_unique_constraint(
        "uq_vehicle_ownerships",
        "vehicle_ownerships",
        ["vehicle_id", "principal_id", "role", "effective_from"],
    )

    # 4. principal_id back to NOT NULL.
    op.alter_column(
        "vehicle_ownerships",
        "principal_id",
        existing_type=UUID(as_uuid=True),
        nullable=False,
    )

    # 5. Drop the new column.
    op.drop_column("vehicle_ownerships", "vehicle_owner_id")
