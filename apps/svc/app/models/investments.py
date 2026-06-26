"""Investments, positions, cash flows, obligations.

The big architectural fix: an investment is the underlying opportunity
(a fund, a property), and `investment_positions` is the M:N junction to
vehicles. A single investment can have multiple positions when brothers
co-invest in parallel, OR one position via a shared LLC whose internal
ownership is captured in vehicle_ownerships.
"""

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


class Investment(Base, AuditableMixin):
    __tablename__ = "investments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    issuer: Mapped[str | None] = mapped_column(String(256), nullable=True)
    asset_class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asset_classes.id"), nullable=False
    )
    sub_category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asset_sub_categories.id"), nullable=True
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active"
    )  # potential | active | closed
    liquidity_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="liquid"
    )  # liquid | illiquid
    lockup_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    card_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    positions: Mapped[list["InvestmentPosition"]] = relationship(
        back_populates="investment", cascade="all, delete-orphan"
    )


class InvestmentPosition(Base, AuditableMixin):
    __tablename__ = "investment_positions"
    __table_args__ = (
        UniqueConstraint(
            "investment_id",
            "vehicle_id",
            "effective_from",
            name="uq_investment_positions",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    investment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investments.id", ondelete="CASCADE"),
        nullable=False,
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    structure: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # parallel_commitment | shared_llc_internal
    commitment_amount: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    funded_amount: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    current_value: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    ownership_pct: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    investment: Mapped[Investment] = relationship(back_populates="positions")


class InvestmentCashFlow(Base, AuditableMixin):
    """Structured ledger — sums for reporting; the card has the narrative version."""

    __tablename__ = "investment_cash_flows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    investment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(20, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    value_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class InvestmentObligation(Base, AuditableMixin):
    """Multi-source: documents, emails, OR Slack chat with the brothers.

    Provenance via source_kind + the matching source_* FK / pointer.
    """

    __tablename__ = "investment_obligations"
    __table_args__ = (
        # At least one source pointer must be set for non-manual sources.
        CheckConstraint(
            "source_kind = 'manual' OR "
            "source_document_id IS NOT NULL OR "
            "source_email_message_id IS NOT NULL OR "
            "(source_slack_ts IS NOT NULL AND source_slack_channel IS NOT NULL)",
            name="ck_investment_obligations_source",
        ),
        Index(
            "investment_obligations_open_idx",
            "due_on",
            postgresql_where="status = 'open'",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    investment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investments.id", ondelete="CASCADE"),
        nullable=False,
    )
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="open"
    )  # open | satisfied | snoozed | cancelled
    # Provenance
    source_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    source_email_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_messages.id"), nullable=True
    )
    source_slack_ts: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_slack_channel: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_principal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("principals.id"), nullable=True
    )
    # Satisfaction
    satisfied_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    satisfied_cash_flow_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investment_cash_flows.id"), nullable=True
    )
    satisfied_by_principal: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("principals.id"), nullable=True
    )
