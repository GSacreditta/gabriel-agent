from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum as PyEnum

Base = declarative_base()

class Frequency(PyEnum):
    ONCE = "once"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"

class TaskStatus(PyEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"

class Entity(Base):
    __tablename__ = "entities"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    entity_type = Column(String(100))  # person, company, organization
    description = Column(Text)
    google_drive_folder_id = Column(String(255))  # Google Drive folder ID
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    tasks = relationship("Task", back_populates="entity")
    obligations = relationship("Obligation", back_populates="entity")
    authorizations = relationship("Authorization", back_populates="entity")
    documents = relationship("DocumentMetadata", back_populates="entity")

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True)
    entity_id = Column(Integer, ForeignKey("entities.id"))
    description = Column(Text, nullable=False)
    priority = Column(String(50))  # high, medium, low
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)
    due_date = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    entity = relationship("Entity", back_populates="tasks")

class Obligation(Base):
    __tablename__ = "obligations"
    
    id = Column(Integer, primary_key=True)
    entity_id = Column(Integer, ForeignKey("entities.id"))
    description = Column(Text, nullable=False)
    frequency = Column(Enum(Frequency))
    due_date = Column(DateTime)
    last_fulfilled = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    entity = relationship("Entity", back_populates="obligations")

class Authorization(Base):
    __tablename__ = "authorizations"
    
    id = Column(Integer, primary_key=True)
    entity_id = Column(Integer, ForeignKey("entities.id"))
    authorization_type = Column(String(100))  # contract, permit, license, etc.
    description = Column(Text)
    expiry_date = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    entity = relationship("Entity", back_populates="authorizations")

class DocumentMetadata(Base):
    __tablename__ = "document_metadata"
    
    id = Column(Integer, primary_key=True)
    entity_id = Column(Integer, ForeignKey("entities.id"))
    file_id = Column(String(255), nullable=False)  # Google Drive file ID
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500))  # Path within Google Drive
    document_type = Column(String(100))  # contract, report, invoice, etc.
    extraction_method = Column(String(50))  # pdf, ocr, etc.
    confidence_score = Column(Float)  # AI confidence in extraction
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    entity = relationship("Entity", back_populates="documents")

class ProcessedFiles(Base):
    """Track files that have already been processed to prevent reprocessing"""
    __tablename__ = "processed_files"
    
    id = Column(Integer, primary_key=True)
    file_id = Column(String(255), nullable=False, unique=True)  # Google Drive file ID
    file_name = Column(String(255), nullable=False)
    entity_id = Column(Integer, ForeignKey("entities.id"))
    processing_status = Column(String(50), default="processed")  # processed, approved, rejected
    original_folder_id = Column(String(255))  # Master folder ID
    current_folder_id = Column(String(255))  # Entity folder ID after moving
    processed_at = Column(DateTime, default=func.now())
    approved_at = Column(DateTime)
    
    # Relationships
    entity = relationship("Entity") 