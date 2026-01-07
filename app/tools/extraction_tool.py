"""
Document Extraction Tool - Comprehensive Text Analysis and Field Extraction
Integrates all document processing logic with confidence scoring and validation
"""

import re
import os
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, date
import tempfile
from dataclasses import dataclass


@dataclass
class ExtractionResult:
    """Structured extraction result with confidence scores"""
    entity_name: str
    entity_confidence: float
    issue_date: Optional[str]
    date_confidence: float
    subject: str
    subject_confidence: float
    summary: str
    document_type: str
    document_type_confidence: float
    extracted_tasks: List[Dict[str, Any]]
    task_confidence: float
    content: str
    file_name: str
    processing_time: float
    extraction_method: str
    raw_metadata: Dict[str, Any]


class DocumentExtractionTool:
    """Comprehensive document extraction tool following document_processor.py patterns"""
    
    def __init__(self):
        """Initialize extraction tool with pattern libraries"""
        
        # Document type patterns
        self.document_patterns = {
            'financial_report': [
                r'quarterly.*report', r'q[1-4].*\d{4}', r'financial.*statement',
                r'earnings.*report', r'annual.*report', r'balance.*sheet'
            ],
            'contract': [
                r'contrato.*mutuo', r'agreement', r'contract', r'mutuo.*loan',
                r'terms.*conditions', r'service.*agreement'
            ],
            'correspondence': [
                r'letter', r'memorandum', r'memo', r'correspondence',
                r'communication', r'message'
            ],
            'invoice': [
                r'invoice', r'bill', r'receipt', r'payment.*request',
                r'statement.*account'
            ],
            'legal': [
                r'authorization', r'power.*attorney', r'legal.*notice',
                r'court.*document', r'affidavit'
            ],
            'administrative': [
                r'form', r'application', r'registration', r'certificate',
                r'permit', r'license'
            ]
        }
        
        # Entity extraction patterns
        self.entity_patterns = [
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Inc|Corp|LLC|Ltd|Limited|Company|Co)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Holdings',
            r'Bank\s+of\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Bank',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Trust'
        ]
        
        # Date patterns
        self.date_patterns = [
            r'(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
            r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
            r'(\w+\s+\d{1,2},?\s+\d{4})',
            r'(\d{1,2}\s+\w+\s+\d{4})'
        ]
        
        # Task indicators
        self.task_indicators = [
            r'(?:please|kindly)\s+(?:provide|submit|send|forward)',
            r'(?:required|need|must)\s+(?:to|by)',
            r'action\s+(?:required|needed|item)',
            r'(?:due|deadline|by)\s+\d',
            r'(?:todo|task):\s*',
            r'(?:complete|submit|review|prepare|update|notify).*by'
        ]
        
    async def extract_document_fields(self, 
                                    content: str, 
                                    file_name: str,
                                    file_metadata: Dict[str, Any] = None) -> ExtractionResult:
        """
        Comprehensive document field extraction with confidence scoring
        """
        start_time = datetime.now()
        
        try:
            # Step 1: Extract entity information
            entity_name, entity_confidence = self._extract_entity_with_confidence(content, file_name)
            
            # Step 2: Extract and validate dates
            issue_date, date_confidence = self._extract_date_with_confidence(content, file_name)
            
            # Step 3: Extract subject/title
            subject, subject_confidence = self._extract_subject_with_confidence(content, file_name)
            
            # Step 4: Classify document type
            doc_type, doc_type_confidence = self._classify_document_type(content, file_name)
            
            # Step 5: Extract tasks and action items
            tasks, task_confidence = self._extract_tasks_with_confidence(content)
            
            # Step 6: Generate summary
            summary = await self._generate_document_summary(content, {
                'entity_name': entity_name,
                'issue_date': issue_date,
                'subject': subject,
                'document_type': doc_type
            })
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return ExtractionResult(
                entity_name=entity_name,
                entity_confidence=entity_confidence,
                issue_date=issue_date,
                date_confidence=date_confidence,
                subject=subject,
                subject_confidence=subject_confidence,
                summary=summary,
                document_type=doc_type,
                document_type_confidence=doc_type_confidence,
                extracted_tasks=tasks,
                task_confidence=task_confidence,
                content=content,
                file_name=file_name,
                processing_time=processing_time,
                extraction_method="comprehensive_extraction",
                raw_metadata=file_metadata or {}
            )
            
        except Exception as e:
            # Return basic extraction result on error
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return ExtractionResult(
                entity_name="Unknown Entity",
                entity_confidence=0.0,
                issue_date=None,
                date_confidence=0.0,
                subject=file_name,
                subject_confidence=0.5,
                summary="Extraction failed - manual review required",
                document_type="Unknown",
                document_type_confidence=0.0,
                extracted_tasks=[],
                task_confidence=0.0,
                content=content,
                file_name=file_name,
                processing_time=processing_time,
                extraction_method="error_fallback",
                raw_metadata={"error": str(e)}
            )
    
    def _extract_entity_with_confidence(self, content: str, file_name: str) -> Tuple[str, float]:
        """Extract entity name with confidence scoring"""
        try:
            # Strategy 1: Extract from filename (highest confidence)
            filename_entity = self._extract_entity_from_filename(file_name)
            if filename_entity != "Unknown":
                return filename_entity, 0.95
            
            # Strategy 2: Pattern matching in content
            for pattern in self.entity_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    entity = self._simplify_entity_name(matches[0])
                    return entity, 0.85
            
            # Strategy 3: Look for capitalized sequences
            lines = content.split('\n')[:10]  # Check first 10 lines
            for line in lines:
                words = line.split()
                for i, word in enumerate(words):
                    if word.isupper() and len(word) > 2:
                        # Check if followed by business indicators
                        if i + 1 < len(words) and words[i + 1].lower() in ['inc', 'corp', 'llc', 'ltd']:
                            return f"{word.title()} {words[i + 1].title()}", 0.75
                        elif len(word) > 4:
                            return word.title(), 0.65
            
            return "Unknown Entity", 0.0
            
        except Exception:
            return "Unknown Entity", 0.0
    
    def _extract_date_with_confidence(self, content: str, file_name: str) -> Tuple[Optional[str], float]:
        """Extract issue date with confidence scoring"""
        try:
            # Strategy 1: Look for dates in filename
            for pattern in self.date_patterns:
                matches = re.findall(pattern, file_name)
                if matches:
                    return matches[0], 0.9
            
            # Strategy 2: Look for dates in content
            for pattern in self.date_patterns:
                matches = re.findall(pattern, content)
                if matches:
                    return matches[0], 0.8
            
            return None, 0.0
            
        except Exception:
            return None, 0.0
    
    def _extract_subject_with_confidence(self, content: str, file_name: str) -> Tuple[str, float]:
        """Extract subject/title with confidence scoring"""
        try:
            # Strategy 1: First line of content (if it looks like a title)
            lines = content.strip().split('\n')
            if lines:
                first_line = lines[0].strip()
                if len(first_line) > 10 and len(first_line) < 100:
                    if not first_line.endswith('.'):  # Titles usually don't end with periods
                        return first_line, 0.8
            
            # Strategy 2: Extract from filename
            return self._extract_document_title(file_name, content), 0.6
            
        except Exception:
            return file_name, 0.5
    
    def _classify_document_type(self, content: str, file_name: str) -> Tuple[str, float]:
        """Classify document type with confidence scoring"""
        try:
            combined_text = f"{file_name} {content}".lower()
            
            for doc_type, patterns in self.document_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, combined_text, re.IGNORECASE):
                        return doc_type.replace('_', ' ').title(), 0.8
            
            return "General Document", 0.5
            
        except Exception:
            return "Unknown", 0.0
    
    def _extract_tasks_with_confidence(self, content: str) -> Tuple[List[Dict[str, Any]], float]:
        """Extract tasks and action items with confidence scoring"""
        try:
            tasks = []
            lines = content.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Check if line contains task indicators
                for pattern in self.task_indicators:
                    if re.search(pattern, line, re.IGNORECASE):
                        task = {
                            "description": line,
                            "type": self._classify_task_type(line),
                            "priority": self._determine_task_priority(line),
                            "due_date": self._extract_due_date_from_line(line)
                        }
                        tasks.append(task)
                        break
            
            confidence = min(0.9, len(tasks) * 0.3) if tasks else 0.0
            return tasks, confidence
            
        except Exception:
            return [], 0.0
    
    def _extract_entity_from_filename(self, file_name: str) -> str:
        """Extract entity name from filename"""
        try:
            # Remove file extension
            name_without_ext = os.path.splitext(file_name)[0]
            
            # Look for known entity patterns in filename
            words = name_without_ext.replace('_', ' ').replace('-', ' ').split()
            
            # Find sequences of capitalized words
            for i, word in enumerate(words):
                if word[0].isupper():
                    entity_parts = [word]
                    for j in range(i + 1, len(words)):
                        if words[j][0].isupper() and not words[j].isdigit():
                            entity_parts.append(words[j])
                        else:
                            break
                    if len(entity_parts) >= 2:
                        return ' '.join(entity_parts)
            
            return "Unknown"
            
        except Exception:
            return "Unknown"
    
    def _simplify_entity_name(self, entity_name: str) -> str:
        """Simplify and clean entity name"""
        try:
            # Remove extra whitespace
            cleaned = ' '.join(entity_name.split())
            
            # Capitalize properly
            words = cleaned.split()
            capitalized_words = []
            for word in words:
                if word.lower() in ['inc', 'corp', 'llc', 'ltd', 'company', 'co', 'holdings', 'bank', 'trust']:
                    capitalized_words.append(word.title())
                else:
                    capitalized_words.append(word.title())
            
            return ' '.join(capitalized_words)
            
        except Exception:
            return entity_name
    
    def _extract_document_title(self, file_name: str, text: str) -> str:
        """Extract document title"""
        try:
            # Try to extract from filename first
            name_without_ext = os.path.splitext(file_name)[0]
            
            # Clean up filename
            title = name_without_ext.replace('_', ' ').replace('-', ' ')
            title = ' '.join(title.split())  # Remove extra spaces
            
            # If filename is too generic, try first line of text
            if len(title) < 10 or title.lower() in ['document', 'file', 'untitled']:
                lines = text.strip().split('\n')
                if lines and len(lines[0].strip()) > 10:
                    return lines[0].strip()
            
            return title.title()
            
        except Exception:
            return file_name
    
    def _is_valid_date(self, date_str: str) -> bool:
        """Validate if string represents a valid date"""
        try:
            # Try different date formats
            for fmt in ['%m/%d/%Y', '%Y-%m-%d', '%B %d, %Y', '%d %B %Y']:
                try:
                    datetime.strptime(date_str, fmt)
                    return True
                except ValueError:
                    continue
            return False
        except Exception:
            return False
    
    def _extract_due_date_from_line(self, line: str) -> Optional[str]:
        """Extract due date from a task line"""
        try:
            # Look for date patterns near "by", "due", "deadline"
            words = line.split()
            for i, word in enumerate(words):
                if word.lower() in ['by', 'due', 'deadline']:
                    # Check next few words for dates
                    for j in range(i + 1, min(i + 4, len(words))):
                        potential_date = ' '.join(words[j:j+3])
                        if self._is_valid_date(potential_date):
                            return potential_date
            
            return None
            
        except Exception:
            return None
    
    def _classify_task_type(self, task_description: str) -> str:
        """Classify task type based on description"""
        try:
            lower_desc = task_description.lower()
            
            if any(word in lower_desc for word in ['review', 'check', 'verify']):
                return "Review"
            elif any(word in lower_desc for word in ['submit', 'send', 'provide']):
                return "Submission"
            elif any(word in lower_desc for word in ['meeting', 'call', 'discuss']):
                return "Communication"
            else:
                return "General"
                
        except Exception:
            return "General"
    
    def _determine_task_priority(self, task_description: str) -> str:
        """Determine task priority based on description"""
        try:
            lower_desc = task_description.lower()
            
            if any(word in lower_desc for word in ['urgent', 'asap', 'immediate']):
                return "High"
            elif any(word in lower_desc for word in ['deadline', 'due']):
                return "Medium"
            else:
                return "Low"
                
        except Exception:
            return "Low"
    
    async def _generate_document_summary(self, text: str, extracted_fields: Dict[str, Any]) -> str:
        """Generate document summary based on extracted fields"""
        try:
            # Create a summary based on extracted information
            entity = extracted_fields.get('entity_name', 'Unknown Entity')
            doc_type = extracted_fields.get('document_type', 'document')
            issue_date = extracted_fields.get('issue_date', 'unknown date')
            
            # Take first 200 characters of content for context
            content_snippet = text[:200].strip()
            if len(text) > 200:
                content_snippet += "..."
            
            summary = f"This {doc_type.lower()} from {entity} dated {issue_date} contains: {content_snippet}"
            
            return summary
            
        except Exception:
            return "Document summary generation failed - manual review required" 