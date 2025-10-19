"""
Database Models - SQLAlchemy models for entities, tasks, obligations, authorizations
"""

from sqlalchemy import Column, String, DateTime, Integer, Date, Text, JSON, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()


class TaskStatus(enum.Enum):
    """Task status enumeration"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class Frequency(enum.Enum):
    """Frequency enumeration for recurring tasks/obligations"""
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"


class Entity(Base):
    """Entity model - represents individuals, organizations, etc."""
    __tablename__ = "entities"
    
    entity_id = Column(String(50), primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    category = Column(String(100))
    contact_info = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Task(Base):
    """Task model - represents actionable tasks"""
    __tablename__ = "tasks"
    
    task_id = Column(String(50), primary_key=True)
    description = Column(Text, nullable=False)
    type = Column(String(100))
    entity_id = Column(String(50))
    due_date = Column(Date)
    frequency = Column(SQLEnum(Frequency))
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime)


class Obligation(Base):
    """Obligation model - represents recurring obligations"""
    __tablename__ = "obligations"
    
    obligation_id = Column(String(50), primary_key=True)
    description = Column(Text, nullable=False)
    entity_id = Column(String(50))
    frequency = Column(SQLEnum(Frequency))
    trigger_date = Column(Date)
    reminder_lead_time = Column(Integer, default=5)
    last_completed = Column(Date)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Authorization(Base):
    """Authorization model - represents permissions and authorizations"""
    __tablename__ = "authorizations"
    
    auth_id = Column(String(50), primary_key=True)
    entity_id = Column(String(50))
    task_type = Column(String(100), nullable=False)
    author = Column(String(255), nullable=False)
    expiry = Column(Date)
    slack_link = Column(String(500))
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DocumentMetadata(Base):
    """Document metadata model - stores document processing information"""
    __tablename__ = "document_metadata"
    
    doc_id = Column(String(50), primary_key=True)
    file_name = Column(String(500), nullable=False)
    file_id = Column(String(255))
    entity_id = Column(String(50))
    entity_name = Column(String(255))
    issue_date = Column(Date)
    subject = Column(Text)
    summary = Column(Text)
    document_type = Column(String(100))
    drive_link = Column(String(500))
    confidence_scores = Column(JSON)
    processing_time = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
