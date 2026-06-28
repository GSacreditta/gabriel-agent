"""People & family branches.

Stern Mazal is NOT a legal entity — these tables describe the human side of
the family office. Family branches roll up principals for the per-family
reporting view.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditableMixin, Base


class FamilyBranch(Base):
    __tablename__ = "family_branches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)

    principals: Mapped[list["Principal"]] = relationship(back_populates="branch")


class Principal(Base, AuditableMixin):
    """A person — principal (Gabriel/Daniel), spouse, or advisor.

    Only is_approver=True principals can authorise HDL gates. Spouses are
    mapped here for legal accuracy and ownership purposes but cannot approve.
    """

    __tablename__ = "principals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    full_name: Mapped[str] = mapped_column(String(128), nullable=False)
    surname_at_birth: Mapped[str | None] = mapped_column(String(128), nullable=True)
    email_primary: Mapped[str | None] = mapped_column(CITEXT(), unique=True, nullable=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)  # principal|spouse|advisor
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("family_branches.id"), nullable=True
    )
    is_approver: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    branch: Mapped[FamilyBranch | None] = relationship(back_populates="principals")
