"""
Extraction Agent - Document Processing Agent
Follows document_processor rules with confidence scoring and HDL review
Phase V Implementation - Comprehensive extraction with real tools
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import json
from .base_agent import BaseAgent
from ..tools.extraction_tool import DocumentExtractionTool, ExtractionResult


class ExtractionAgent(BaseAgent):
    """Extraction Agent for document processing and content extraction"""
    
    def __init__(self):
        super().__init__("EXTRACTION_AGENT")
        
        # Initialize comprehensive extraction tool
        self.extraction_tool = DocumentExtractionTool()
        
        # Extraction strategies by document type
        self.extraction_strategies = {
            'financial_report': self._process_financial_document,
            'contract': self._process_contract_document,
            'correspondence': self._process_correspondence_document,
            'invoice': self._process_invoice_document,
            'legal': self._process_legal_document,
            'administrative': self._process_administrative_document,
            'email': self._process_email_document
        }
        
        # Confidence thresholds for HDL review
        self.confidence_thresholds = {
            'entity_confidence': 0.70,
            'subject_confidence': 0.60,
            'document_type_confidence': 0.50,
            'task_confidence': 0.65,
            'overall_confidence': 0.70
        }
    
    def connect_agent(self, agent_type: str, agent_instance):
        """Connect to another agent"""
        self.log_activity(f"Connected to {agent_type}", {"agent_type": agent_type})
    
    async def health_check(self) -> bool:
        """Check if the agent is healthy"""
        try:
            # Basic health check - agent is healthy if extraction tool is available
            return self.extraction_tool is not None
        except Exception as e:
            self.log_activity("Health check failed", {"error": str(e)})
            return False
        
    async def get_capabilities(self) -> List[str]:
        """Return Extraction Agent capabilities"""
        return [
            "comprehensive_document_extraction",
            "confidence_scoring",
            "document_type_classification",
            "entity_extraction",
            "task_extraction",
            "email_processing",
            "hdl_review_submission",
            "content_chunking",
            "metadata_extraction"
        ]
    
    async def handle_message(self, source_agent: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle messages from other agents"""
        action = message.get('action')
        data = message.get('data', {})
        
        try:
            if action == "extract_document":
                result = await self.extract_document(data)
                return {"status": "success", "result": result}
                
            elif action == "process_email":
                result = await self.process_email(data)
                return {"status": "success", "result": result}
                
            elif action == "extract_with_ocr":
                result = await self.extract_with_ocr_content(data)
                return {"status": "success", "result": result}
                
            elif action == "reprocess_with_corrections":
                result = await self.reprocess_with_human_corrections(data)
                return {"status": "success", "result": result}
                
            else:
                return {"status": "error", "message": f"Unknown action: {action}"}
                
        except Exception as e:
            self.logger.error(f"Error handling message: {e}")
            return {"status": "error", "message": str(e)}
    
    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute extraction tasks"""
        task_type = task.get('type')
        
        if task_type == "batch_extraction":
            return await self.batch_extract_documents(task.get('file_list', []))
        elif task_type == "confidence_review":
            return await self.review_low_confidence_extractions(task.get('extraction_id'))
        else:
            return {"status": "error", "message": f"Unknown task type: {task_type}"}
    
    async def extract_document(self, document_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main document extraction method with comprehensive Phase V implementation
        ALL extractions go to HDL Agent for review (per requirements)
        """
        try:
            file_name = document_data.get('file_name', '')
            content = document_data.get('content', '')
            file_metadata = document_data.get('file_metadata', {})
            
            self.log_activity("Document extraction started", {
                "file_name": file_name,
                "content_length": len(content)
            })
            
            # Step 1: Comprehensive extraction using extraction tool
            extraction_result = await self.extraction_tool.extract_document_fields(
                content=content,
                file_name=file_name,
                file_metadata=file_metadata
            )
            
            # Step 2: Apply document-type specific processing
            specialized_result = await self._apply_specialized_extraction(extraction_result)
            
            # Step 3: Calculate overall confidence and prepare for review
            overall_confidence = self._calculate_overall_confidence(specialized_result)
            
            # Step 4: Prepare extraction output with comprehensive metadata
            extraction_output = {
                'file_name': file_name,
                'entity_name': specialized_result.entity_name,
                'entity_confidence': specialized_result.entity_confidence,
                'issue_date': specialized_result.issue_date,
                'date_confidence': specialized_result.date_confidence,
                'subject': specialized_result.subject,
                'subject_confidence': specialized_result.subject_confidence,
                'summary': specialized_result.summary,
                'document_type': specialized_result.document_type,
                'document_type_confidence': specialized_result.document_type_confidence,
                'extracted_tasks': specialized_result.extracted_tasks,
                'task_confidence': specialized_result.task_confidence,
                'content': specialized_result.content,
                'processing_time': specialized_result.processing_time,
                'extraction_method': specialized_result.extraction_method,
                'overall_confidence': overall_confidence,
                'confidence_scores': {
                    'entity': specialized_result.entity_confidence,
                    'subject': specialized_result.subject_confidence,
                    'document_type': specialized_result.document_type_confidence,
                    'date': specialized_result.date_confidence,
                    'tasks': specialized_result.task_confidence,
                    'overall': overall_confidence
                },
                'extraction_timestamp': datetime.utcnow().isoformat(),
                'drive_link': file_metadata.get('webViewLink', ''),
                'requires_review': self._requires_human_review(overall_confidence, specialized_result)
            }
            
            # Step 5: ALL extractions go to HDL Agent for review (Phase V requirement)
            hdl_response = await self.send_message("HDL_AGENT", {
                "action": "request_review",
                "data": {
                    "type": "extraction_review",
                    "extraction_data": extraction_output,
                    "priority": "high" if overall_confidence < 0.6 else "normal",
                    "message": f"Review extraction for: {file_name} (Confidence: {overall_confidence:.2f})"
                }
            })
            
            # Step 6: Pass to Storage Agent for vector storage
            storage_response = await self.send_message("STORAGE_AGENT", {
                "action": "store_extraction",
                "data": extraction_output
            })
            
            self.log_activity("Document extraction completed", {
                "file_name": file_name,
                "entity_name": specialized_result.entity_name,
                "overall_confidence": overall_confidence,
                "requires_review": extraction_output['requires_review']
            })
            
            return {
                "status": "completed",
                "extraction_data": extraction_output,
                "hdl_review": hdl_response,
                "storage_result": storage_response,
                "confidence_analysis": self._generate_confidence_analysis(specialized_result)
            }
            
        except Exception as e:
            self.logger.error(f"Error extracting document: {e}")
            return {"status": "error", "message": str(e)}
    
    async def process_email(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process email and attachments as separate documents
        Handle password-protected attachments by requesting HDL help
        """
        try:
            email_subject = email_data.get('subject', '')
            email_content = email_data.get('content', '')
            attachments = email_data.get('attachments', [])
            
            self.log_activity("Email processing started", {
                "subject": email_subject,
                "attachments_count": len(attachments)
            })
            
            results = []
            
            # Process the email itself as a document
            email_extraction = await self.extract_document({
                'file_name': f"email_{email_subject}.txt",
                'content': f"Subject: {email_subject}\n\n{email_content}",
                'file_metadata': {
                    'document_type': 'email',
                    'source': 'email_processing'
                }
            })
            results.append({"type": "email", "extraction": email_extraction})
            
            # Process each attachment separately
            for attachment in attachments:
                attachment_name = attachment.get('name', 'unknown_attachment')
                
                if attachment.get('password_protected'):
                    # Request HDL help for password-protected attachments
                    hdl_response = await self.send_message("HDL_AGENT", {
                        "action": "request_review",
                        "data": {
                            "type": "password_assistance",
                            "attachment_info": attachment,
                            "priority": "high",
                            "message": f"Password required for attachment: {attachment_name}"
                        }
                    })
                    results.append({
                        "type": "password_protected",
                        "attachment_name": attachment_name,
                        "hdl_request": hdl_response
                    })
                else:
                    # Process attachment normally
                    attachment_content = attachment.get('content', '')
                    attachment_extraction = await self.extract_document({
                        'file_name': attachment_name,
                        'content': attachment_content,
                        'file_metadata': {
                            'document_type': 'email_attachment',
                            'parent_email': email_subject,
                            'source': 'email_attachment'
                        }
                    })
                    results.append({
                        "type": "attachment",
                        "extraction": attachment_extraction
                    })
            
            return {
                "status": "completed",
                "email_subject": email_subject,
                "processed_items": results,
                "total_extractions": len([r for r in results if r["type"] in ["email", "attachment"]])
            }
            
        except Exception as e:
            self.logger.error(f"Error processing email: {e}")
            return {"status": "error", "message": str(e)}
    
    async def extract_with_ocr_content(self, ocr_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract from OCR-processed content with additional validation"""
        try:
            # Apply OCR-specific confidence adjustments
            ocr_confidence = ocr_data.get('ocr_confidence', 1.0)
            
            # Reduce confidence scores based on OCR quality
            confidence_adjustment = min(ocr_confidence, 0.9)  # Max 90% for OCR content
            
            extraction_result = await self.extract_document(ocr_data)
            
            # Adjust confidence scores
            if extraction_result.get('status') == 'completed':
                extraction_data = extraction_result['extraction_data']
                for key in ['entity_confidence', 'subject_confidence', 'document_type_confidence', 'date_confidence', 'task_confidence']:
                    if key in extraction_data:
                        extraction_data[key] *= confidence_adjustment
                
                extraction_data['overall_confidence'] *= confidence_adjustment
                extraction_data['extraction_method'] = f"ocr_extraction (confidence: {ocr_confidence:.2f})"
            
            return extraction_result
            
        except Exception as e:
            self.logger.error(f"Error extracting OCR content: {e}")
            return {"status": "error", "message": str(e)}
    
    async def reprocess_with_human_corrections(self, correction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Reprocess document with human corrections applied"""
        try:
            original_extraction = correction_data.get('original_extraction', {})
            human_corrections = correction_data.get('corrections', {})
            
            # Apply human corrections to improve extraction
            corrected_extraction = original_extraction.copy()
            
            for field, correction in human_corrections.items():
                if field in corrected_extraction:
                    corrected_extraction[field] = correction
                    # Boost confidence for human-corrected fields
                    confidence_field = f"{field}_confidence"
                    if confidence_field in corrected_extraction:
                        corrected_extraction[confidence_field] = 0.98  # High confidence for human corrections
            
            corrected_extraction['extraction_method'] = "human_corrected"
            corrected_extraction['human_corrections'] = human_corrections
            
            # Resubmit to Storage Agent with corrections
            storage_response = await self.send_message("STORAGE_AGENT", {
                "action": "store_extraction",
                "data": corrected_extraction
            })
            
            return {
                "status": "completed",
                "corrected_extraction": corrected_extraction,
                "storage_result": storage_response
            }
            
        except Exception as e:
            self.logger.error(f"Error reprocessing with corrections: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _apply_specialized_extraction(self, extraction_result: ExtractionResult) -> ExtractionResult:
        """Apply document-type specific extraction strategies"""
        doc_type = extraction_result.document_type.lower().replace(' ', '_')
        
        if doc_type in self.extraction_strategies:
            strategy_func = self.extraction_strategies[doc_type]
            return await strategy_func(extraction_result)
        else:
            # Default processing for unknown document types
            return extraction_result
    
    async def _process_financial_document(self, extraction_result: ExtractionResult) -> ExtractionResult:
        """Specialized processing for financial documents"""
        # Look for financial-specific patterns
        content = extraction_result.content.lower()
        
        # Enhance entity extraction for financial documents
        if 'quarterly' in content or any(q in extraction_result.file_name.lower() for q in ['q1', 'q2', 'q3', 'q4']):
            extraction_result.subject_confidence = min(0.95, extraction_result.subject_confidence + 0.1)
        
        # Look for financial metrics
        financial_keywords = ['revenue', 'profit', 'loss', 'earnings', 'assets', 'liabilities']
        if any(keyword in content for keyword in financial_keywords):
            extraction_result.document_type_confidence = min(0.95, extraction_result.document_type_confidence + 0.15)
        
        return extraction_result
    
    async def _process_contract_document(self, extraction_result: ExtractionResult) -> ExtractionResult:
        """Specialized processing for contract documents"""
        content = extraction_result.content.lower()
        
        # Look for contract-specific terms
        contract_terms = ['agreement', 'terms', 'conditions', 'party', 'whereas', 'therefore']
        if any(term in content for term in contract_terms):
            extraction_result.document_type_confidence = min(0.95, extraction_result.document_type_confidence + 0.2)
        
        # Contracts typically have high importance for task extraction
        if extraction_result.extracted_tasks:
            extraction_result.task_confidence = min(0.95, extraction_result.task_confidence + 0.1)
        
        return extraction_result
    
    async def _process_correspondence_document(self, extraction_result: ExtractionResult) -> ExtractionResult:
        """Specialized processing for correspondence documents"""
        return extraction_result  # Basic processing for now
    
    async def _process_invoice_document(self, extraction_result: ExtractionResult) -> ExtractionResult:
        """Specialized processing for invoice documents"""
        return extraction_result  # Basic processing for now
    
    async def _process_legal_document(self, extraction_result: ExtractionResult) -> ExtractionResult:
        """Specialized processing for legal documents"""
        return extraction_result  # Basic processing for now
    
    async def _process_administrative_document(self, extraction_result: ExtractionResult) -> ExtractionResult:
        """Specialized processing for administrative documents"""
        return extraction_result  # Basic processing for now
    
    async def _process_email_document(self, extraction_result: ExtractionResult) -> ExtractionResult:
        """Specialized processing for email documents"""
        # Emails often have clear subjects
        if extraction_result.subject.startswith('Subject:'):
            extraction_result.subject_confidence = min(0.95, extraction_result.subject_confidence + 0.1)
        
        return extraction_result
    
    def _calculate_overall_confidence(self, extraction_result: ExtractionResult) -> float:
        """Calculate overall confidence score based on all individual confidences"""
        confidences = [
            extraction_result.entity_confidence * 0.25,  # Entity is important
            extraction_result.subject_confidence * 0.20,  # Subject is important
            extraction_result.document_type_confidence * 0.15,  # Type classification
            extraction_result.date_confidence * 0.15,  # Date extraction
            extraction_result.task_confidence * 0.25  # Task extraction is crucial
        ]
        
        return sum(confidences)
    
    def _requires_human_review(self, overall_confidence: float, extraction_result: ExtractionResult) -> bool:
        """Determine if extraction requires human review based on confidence thresholds"""
        # Check overall confidence
        if overall_confidence < self.confidence_thresholds['overall_confidence']:
            return True
        
        # Check individual confidence thresholds
        if extraction_result.entity_confidence < self.confidence_thresholds['entity_confidence']:
            return True
        
        if extraction_result.subject_confidence < self.confidence_thresholds['subject_confidence']:
            return True
        
        if extraction_result.document_type_confidence < self.confidence_thresholds['document_type_confidence']:
            return True
        
        if extraction_result.task_confidence < self.confidence_thresholds['task_confidence'] and extraction_result.extracted_tasks:
            return True
        
        return False
    
    def _generate_confidence_analysis(self, extraction_result: ExtractionResult) -> Dict[str, Any]:
        """Generate detailed confidence analysis for review"""
        overall_confidence = self._calculate_overall_confidence(extraction_result)
        
        return {
            "overall_confidence": overall_confidence,
            "confidence_breakdown": {
                "entity": {
                    "score": extraction_result.entity_confidence,
                    "threshold": self.confidence_thresholds['entity_confidence'],
                    "status": "pass" if extraction_result.entity_confidence >= self.confidence_thresholds['entity_confidence'] else "review_needed"
                },
                "subject": {
                    "score": extraction_result.subject_confidence,
                    "threshold": self.confidence_thresholds['subject_confidence'],
                    "status": "pass" if extraction_result.subject_confidence >= self.confidence_thresholds['subject_confidence'] else "review_needed"
                },
                "document_type": {
                    "score": extraction_result.document_type_confidence,
                    "threshold": self.confidence_thresholds['document_type_confidence'],
                    "status": "pass" if extraction_result.document_type_confidence >= self.confidence_thresholds['document_type_confidence'] else "review_needed"
                },
                "tasks": {
                    "score": extraction_result.task_confidence,
                    "threshold": self.confidence_thresholds['task_confidence'],
                    "status": "pass" if extraction_result.task_confidence >= self.confidence_thresholds['task_confidence'] else "review_needed"
                }
            },
            "extraction_quality": "high" if overall_confidence >= 0.8 else "medium" if overall_confidence >= 0.6 else "low",
            "recommendations": self._generate_quality_recommendations(extraction_result, overall_confidence)
        }
    
    def _generate_quality_recommendations(self, extraction_result: ExtractionResult, overall_confidence: float) -> List[str]:
        """Generate recommendations for improving extraction quality"""
        recommendations = []
        
        if extraction_result.entity_confidence < 0.7:
            recommendations.append("Entity extraction needs verification - consider manual review")
        
        if extraction_result.document_type_confidence < 0.6:
            recommendations.append("Document type classification uncertain - may need reclassification")
        
        if extraction_result.task_confidence < 0.6 and extraction_result.extracted_tasks:
            recommendations.append("Task extraction has low confidence - verify action items")
        
        if overall_confidence < 0.5:
            recommendations.append("Overall extraction quality is low - recommend manual processing")
        
        if not recommendations:
            recommendations.append("Extraction quality is good - minimal review needed")
        
        return recommendations
    
    async def batch_extract_documents(self, file_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process multiple documents in batch"""
        try:
            results = []
            successful_extractions = 0
            failed_extractions = 0
            
            for file_data in file_list:
                try:
                    extraction_result = await self.extract_document(file_data)
                    results.append(extraction_result)
                    if extraction_result.get('status') == 'completed':
                        successful_extractions += 1
                    else:
                        failed_extractions += 1
                except Exception as e:
                    failed_extractions += 1
                    results.append({
                        "status": "error",
                        "file_name": file_data.get('file_name', 'unknown'),
                        "error": str(e)
                    })
            
            return {
                "status": "completed",
                "total_files": len(file_list),
                "successful_extractions": successful_extractions,
                "failed_extractions": failed_extractions,
                "results": results
            }
            
        except Exception as e:
            self.logger.error(f"Error in batch extraction: {e}")
            return {"status": "error", "message": str(e)} 