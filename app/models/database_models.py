"""
Database Models - SQLAlchemy models for entities, investments, tasks, obligations, and related records.

Task 1.1 consolidates legacy definitions and introduces the extended schema
outlined in the SM18z PRD and MVP ADR documents.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict
import enum

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class EntityType(enum.Enum):
    """Entity type enumeration as described in PRD Section 3."""

    TRUST = "trust"
    LLC = "llc"
    PERSONAL = "personal"
    OTHER = "other"


class TaskStatus(enum.Enum):
    """Task status enumeration."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class Frequency(enum.Enum):
    """Frequency enumeration for recurring tasks/obligations."""

    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"


class InvestmentStatus(enum.Enum):
    """Investment lifecycle states."""

    POTENTIAL = "potential"
    ACTIVE = "active"
    CLOSED = "closed"


class InvestmentCategory(enum.Enum):
    """Investment categories used across dashboards and ingestion."""

    CASH = "cash"
    FIXED_INCOME = "fixed_income"
    EQUITIES = "equities"
    ALTERNATIVE = "alternative"
    DIGITAL_ASSETS = "digital_assets"
    COMMODITIES = "commodities"
    REAL_ESTATE = "real_estate"
    PRIVATE_CREDIT_LENDING = "private_credit_lending"
    PRIVATE_EQUITY = "private_equity"
    REAL_ASSETS = "real_assets"
    OPERATING_BUSINESS = "operating_business"

    @property
    def display_label(self) -> str:
        labels = {
            InvestmentCategory.CASH: "Cash",
            InvestmentCategory.FIXED_INCOME: "Fixed Income",
            InvestmentCategory.EQUITIES: "Equities",
            InvestmentCategory.ALTERNATIVE: "Alternative",
            InvestmentCategory.DIGITAL_ASSETS: "Digital Assets",
            InvestmentCategory.COMMODITIES: "Commodities",
            InvestmentCategory.REAL_ESTATE: "Real Estate",
            InvestmentCategory.PRIVATE_CREDIT_LENDING: "Private Credit / Lending",
            InvestmentCategory.PRIVATE_EQUITY: "Private Equity",
            InvestmentCategory.REAL_ASSETS: "Real Assets",
            InvestmentCategory.OPERATING_BUSINESS: "Operating Business",
        }
        return labels[self]


CATEGORY_COLOR_MAP: Dict[InvestmentCategory, str] = {
    InvestmentCategory.CASH: "#0ea5e9",
    InvestmentCategory.FIXED_INCOME: "#1d4ed8",
    InvestmentCategory.EQUITIES: "#9333ea",
    InvestmentCategory.ALTERNATIVE: "#f59e0b",
    InvestmentCategory.DIGITAL_ASSETS: "#e11d48",
    InvestmentCategory.COMMODITIES: "#f97316",
    InvestmentCategory.REAL_ESTATE: "#22c55e",
    InvestmentCategory.PRIVATE_CREDIT_LENDING: "#7c3aed",
    InvestmentCategory.PRIVATE_EQUITY: "#d946ef",
    InvestmentCategory.REAL_ASSETS: "#facc15",
    InvestmentCategory.OPERATING_BUSINESS: "#64748b",
}


class Entity(Base):
    """Entity model - represents legal entities such as trusts, LLCs, or personal accounts."""

    __tablename__ = "entities"

    entity_id = Column(String(50), primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    entity_type = Column(SQLEnum(EntityType, name="entity_type_enum"))
    # Legacy category field retained for backward compatibility (to be migrated to entity_type).
    category = Column(String(100))
    ownership_split = Column(JSON)
    formation_docs_link = Column(String(500))
    ein_tax_id = Column(String(50))
    google_drive_folder_id = Column(String(255))
    contact_info = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    investments = relationship("Investment", back_populates="entity")
    tasks = relationship("Task", back_populates="entity")
    obligations = relationship("Obligation", back_populates="entity")
    authorizations = relationship("Authorization", back_populates="entity")
    documents = relationship("DocumentMetadata", back_populates="entity")


class Investment(Base):
    """Investment model - links investments to entities and tracks performance metrics."""

    __tablename__ = "investments"

    investment_id = Column(String(50), primary_key=True)
    short_name = Column(String(255), nullable=False)
    fund_operator = Column(String(255))
    entity_id = Column(String(50), ForeignKey("entities.entity_id"), nullable=False)
    external_id = Column(String(100))  # Original investment identifier from source docs
    commitment_amount = Column(Float)
    subscription_date = Column(Date)
    amount_called = Column(Float)
    category = Column(
        SQLEnum(InvestmentCategory, name="investment_category_enum"), nullable=False
    )
    status = Column(
        SQLEnum(InvestmentStatus, name="investment_status_enum"),
        default=InvestmentStatus.POTENTIAL,
        nullable=False,
    )
    expected_irr = Column(Float)
    actual_irr = Column(Float)
    interest_rate = Column(Float)
    notes = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    entity = relationship("Entity", back_populates="investments")
    documents = relationship("DocumentMetadata", back_populates="investment")
    tasks = relationship("Task", back_populates="investment")
    obligations = relationship("Obligation", back_populates="investment")


class DocumentMetadata(Base):
    """Document metadata model - stores document ingestion and extraction details."""

    __tablename__ = "document_metadata"

    doc_id = Column(String(50), primary_key=True)
    file_name = Column(String(500), nullable=False)
    file_id = Column(String(255))
    entity_id = Column(String(50), ForeignKey("entities.entity_id"))
    entity_name = Column(String(255))
    investment_id = Column(String(50), ForeignKey("investments.investment_id"))
    google_drive_link = Column(String(500))
    issue_date = Column(Date)
    upload_date = Column(DateTime)
    document_language = Column(String(10))
    subject = Column(Text)
    two_line_summary = Column(Text)
    summary = Column(Text)
    document_type = Column(String(100))
    tags = Column(JSON)
    extracted_fields = Column(JSON)
    drive_link = Column(String(500))
    confidence_scores = Column(JSON)
    vector_store_key = Column(String(255))
    processing_time = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    entity = relationship("Entity", back_populates="documents")
    investment = relationship("Investment", back_populates="documents")
    tasks = relationship("Task", back_populates="linked_document")
    obligations = relationship("Obligation", back_populates="linked_document")


class Task(Base):
    """Task model - represents actionable tasks tied to entities and investments."""

    __tablename__ = "tasks"

    task_id = Column(String(50), primary_key=True)
    description = Column(Text, nullable=False)
    type = Column(String(100))
    entity_id = Column(String(50), ForeignKey("entities.entity_id"))
    investment_id = Column(String(50), ForeignKey("investments.investment_id"))
    linked_document_id = Column(String(50), ForeignKey("document_metadata.doc_id"))
    due_date = Column(Date)
    frequency = Column(SQLEnum(Frequency, name="task_frequency_enum"))
    status = Column(
        SQLEnum(TaskStatus, name="task_status_enum"), default=TaskStatus.PENDING
    )
    reminder_settings = Column(JSON)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    completed_at = Column(DateTime)

    entity = relationship("Entity", back_populates="tasks")
    investment = relationship("Investment", back_populates="tasks")
    linked_document = relationship(
        "DocumentMetadata", back_populates="tasks", foreign_keys=[linked_document_id]
    )


class Obligation(Base):
    """Obligation model - represents recurring obligations linked to investments."""

    __tablename__ = "obligations"

    obligation_id = Column(String(50), primary_key=True)
    description = Column(Text, nullable=False)
    entity_id = Column(String(50), ForeignKey("entities.entity_id"))
    investment_id = Column(String(50), ForeignKey("investments.investment_id"))
    linked_document_id = Column(String(50), ForeignKey("document_metadata.doc_id"))
    frequency = Column(SQLEnum(Frequency, name="obligation_frequency_enum"))
    trigger_date = Column(Date)
    reminder_lead_time = Column(Integer, default=5)
    last_completed = Column(Date)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    entity = relationship("Entity", back_populates="obligations")
    investment = relationship("Investment", back_populates="obligations")
    linked_document = relationship(
        "DocumentMetadata",
        foreign_keys=[linked_document_id],
        back_populates="obligations",
    )


class Authorization(Base):
    """Authorization model - represents permissions and HDL approvals."""

    __tablename__ = "authorizations"

    auth_id = Column(String(50), primary_key=True)
    entity_id = Column(String(50), ForeignKey("entities.entity_id"))
    investment_id = Column(String(50), ForeignKey("investments.investment_id"))
    task_type = Column(String(100), nullable=False)
    author = Column(String(255), nullable=False)
    expiry = Column(Date)
    slack_link = Column(String(500))
    description = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    entity = relationship("Entity", back_populates="authorizations")
    investment = relationship("Investment")


class ProcessedFile(Base):
    """Track files that have already been processed to prevent reprocessing."""

    __tablename__ = "processed_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(String(255), nullable=False, unique=True)
    file_name = Column(String(255), nullable=False)
    entity_id = Column(String(50), ForeignKey("entities.entity_id"))
    investment_id = Column(String(50), ForeignKey("investments.investment_id"))
    processing_status = Column(String(50), default="processed")
    original_folder_id = Column(String(255))
    current_folder_id = Column(String(255))
    processed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    approved_at = Column(DateTime)


__all__ = [
    "Authorization",
    "Base",
    "CATEGORY_COLOR_MAP",
    "DocumentMetadata",
    "Entity",
    "EntityType",
    "Frequency",
    "Investment",
    "InvestmentCategory",
    "InvestmentStatus",
    "Obligation",
    "ProcessedFile",
    "Task",
    "TaskStatus",
]
