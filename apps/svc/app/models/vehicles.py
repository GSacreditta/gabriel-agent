"""Vehicles (legal entities) and their ownership graph."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditableMixin, Base


class VehicleType(Base):
    __tablename__ = "vehicle_types"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)


class Vehicle(Base, AuditableMixin):
    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    legal_name: Mapped[str] = mapped_column(String(256), nullable=False)
    short_name: Mapped[str] = mapped_column(String(64), nullable=False)
    vehicle_type_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicle_types.id"), nullable=True
    )
    # Administrative tag: which family this vehicle is associated with for
    # per-family reporting (view C). NULL = shared / umbrella vehicle (e.g.,
    # SM18 LLC, 7Stern) which only shows in SMFO aggregate + per-vehicle views.
    # NOT a beneficiary chain — purely a vehicle-level label.
    family_branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("family_branches.id"), nullable=True
    )
    tax_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # encrypted at rest
    jurisdiction: Mapped[str | None] = mapped_column(String(32), nullable=True)
    formed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    closed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    drive_folder_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    ownerships: Mapped[list["VehicleOwnership"]] = relationship(
        back_populates="vehicle",
        cascade="all, delete-orphan",
        foreign_keys="VehicleOwnership.vehicle_id",
    )


class VehicleOwnership(Base, AuditableMixin):
    """Who controls a vehicle and at what %.

    Owner is EITHER a principal (a person) OR another vehicle (a trust holds
    membership in an LLC, e.g., 7Stern has D&V IRR Trust as a 25% member).
    Exactly one of principal_id / vehicle_owner_id is set per row.

    Time-bounded: effective_to=NULL means current. A spouse might be a trustee
    of an irrevocable trust without economic interest (ownership_pct=NULL).
    """

    __tablename__ = "vehicle_ownerships"
    __table_args__ = (
        CheckConstraint(
            "(principal_id IS NOT NULL)::int + (vehicle_owner_id IS NOT NULL)::int = 1",
            name="ck_vehicle_ownerships_owner_xor",
        ),
        CheckConstraint(
            "vehicle_owner_id IS NULL OR vehicle_owner_id <> vehicle_id",
            name="ck_vehicle_ownerships_no_self_own",
        ),
        # Partial uniques: avoid double-counting the same owner twice on a
        # vehicle for the same role + effective_from. Two indexes because we
        # can't put NULLs in a multi-column unique on PG and expect dedup.
        Index(
            "uq_vehicle_ownerships_by_principal",
            "vehicle_id",
            "principal_id",
            "role",
            "effective_from",
            unique=True,
            postgresql_where="principal_id IS NOT NULL",
        ),
        Index(
            "uq_vehicle_ownerships_by_vehicle",
            "vehicle_id",
            "vehicle_owner_id",
            "role",
            "effective_from",
            unique=True,
            postgresql_where="vehicle_owner_id IS NOT NULL",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="CASCADE"),
        nullable=False,
    )
    # XOR: exactly one owner kind
    principal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("principals.id"), nullable=True
    )
    vehicle_owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    ownership_pct: Mapped[float | None] = mapped_column(Numeric(7, 4), nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    vehicle: Mapped[Vehicle] = relationship(
        back_populates="ownerships", foreign_keys=[vehicle_id]
    )
