"""SQLAlchemy models — all importable for Alembic autogeneration."""

from app.models.base import AuditableMixin, Base, TimestampMixin
from app.models.documents import Document, DocumentLink
from app.models.emails import (
    EmailAccount,
    EmailMessage,
    EmailSender,
    EmailSubjectPattern,
    EmailThread,
)
from app.models.investments import (
    Investment,
    InvestmentCashFlow,
    InvestmentObligation,
    InvestmentPosition,
)
from app.models.principals import FamilyBranch, Principal
from app.models.system import AuditLog, HdlReview, WorkflowRun
from app.models.taxonomy import AssetClass, AssetSubCategory, TaxonomyAudit
from app.models.vehicles import Vehicle, VehicleOwnership, VehicleType

__all__ = [
    "Base",
    "TimestampMixin",
    "AuditableMixin",
    "FamilyBranch",
    "Principal",
    "VehicleType",
    "Vehicle",
    "VehicleOwnership",
    "AssetClass",
    "AssetSubCategory",
    "TaxonomyAudit",
    "Investment",
    "InvestmentPosition",
    "InvestmentCashFlow",
    "InvestmentObligation",
    "Document",
    "DocumentLink",
    "EmailAccount",
    "EmailSender",
    "EmailSubjectPattern",
    "EmailThread",
    "EmailMessage",
    "HdlReview",
    "WorkflowRun",
    "AuditLog",
]
