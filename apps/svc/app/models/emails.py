"""Email intake — multi-account per principal.

A principal can have multiple email_accounts (primary + secondary, e.g.,
personal Gmail + Workspace `gabriel@sternmz8.com`). A single sender can email
both brothers; threads dedupe across accounts via conversation_key (a hash of
normalised subject + sender pair).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditableMixin, Base


class EmailAccount(Base, AuditableMixin):
    __tablename__ = "email_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    principal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("principals.id"), nullable=False
    )
    email_address: Mapped[str] = mapped_column(CITEXT(), unique=True, nullable=False)
    account_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="primary"
    )  # primary | secondary
    provider: Mapped[str] = mapped_column(
        String(16), nullable=False, default="gmail"
    )
    oauth_subject: Mapped[str] = mapped_column(String(128), nullable=False)
    last_history_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class EmailSender(Base, AuditableMixin):
    """Sender Registry — allow / block / triage buckets.

    `domain` is required; `address` is optional (many entries are domain-level).
    Day-15 seed from the inventory CSV preclassifies ~80 senders.
    """

    __tablename__ = "email_senders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    address: Mapped[str | None] = mapped_column(CITEXT(), unique=True, nullable=True)
    domain: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # allow | block | triage
    category: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )  # fund_manager | fund_admin | bank | legal_tax | personal | noise
    default_investment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investments.id"), nullable=True
    )
    default_vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=True
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("principals.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    seed_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class EmailSubjectPattern(Base, AuditableMixin):
    __tablename__ = "email_subject_patterns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pattern: Mapped[str] = mapped_column(String(512), nullable=False)
    pattern_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="substring"
    )  # substring | regex
    intent: Mapped[str | None] = mapped_column(String(64), nullable=True)


class EmailThread(Base, AuditableMixin):
    __tablename__ = "email_threads"
    __table_args__ = (
        UniqueConstraint(
            "gmail_thread_id", "account_id", name="uq_email_threads_per_account"
        ),
        Index("email_threads_conversation_key_idx", "conversation_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    gmail_thread_id: Mapped[str] = mapped_column(String(64), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_accounts.id"), nullable=False
    )
    subject: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    conversation_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    investment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investments.id"), nullable=True
    )
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")


class EmailMessage(Base, AuditableMixin):
    __tablename__ = "email_messages"
    __table_args__ = (
        UniqueConstraint(
            "gmail_message_id", "account_id", name="uq_email_messages_per_account"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("email_threads.id", ondelete="CASCADE"),
        nullable=False,
    )
    gmail_message_id: Mapped[str] = mapped_column(String(64), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_accounts.id"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(16), nullable=False)  # inbound | outbound
    from_address: Mapped[str] = mapped_column(CITEXT(), nullable=False)
    to_addresses: Mapped[list[str]] = mapped_column(ARRAY(CITEXT()), nullable=False)
    cc_addresses: Mapped[list[str]] = mapped_column(
        ARRAY(CITEXT()), nullable=False, server_default="{}"
    )
    subject: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_attachments: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ingest_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending"
    )
