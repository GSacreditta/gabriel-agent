# app/services/document_processor.py

from typing import Dict, Any, List, Optional
import logging
from .vector_storage_service import VectorStorageService
from .embedding_service import EmbeddingService
from datetime import datetime
from .ocr_service import OCRService
from .google_drive import GoogleDriveService
from .agent import Agent
from .slack_service import SlackService
from .pdf_service import PDFService
import json
import os
import tempfile
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class WorkflowState:
    # Core identifiers
    workflow_id: str
    source_type: str  # "file" or "email"
    source_id: str    # file_id or email_id
    
    # Email-specific fields
    email_content: Optional[Dict[str, Any]] = None
    email_attachments: Optional[List[Dict[str, Any]]] = None
    attachment_processing_results: Optional[List[Dict[str, Any]]] = None
    
    # File processing (existing)
    file_id: Optional[str] = None
    file_metadata: Optional[Dict[str, Any]] = None
    
    # Combined content analysis
    combined_text: Optional[str] = None
    content_analysis: Optional[Dict[str, Any]] = None
    
    # Entity matching
    matched_entities: Optional[List[Dict[str, Any]]] = None
    suggested_new_entities: Optional[List[Dict[str, Any]]] = None
    
    # Proposed database records
    proposed_tasks: Optional[List[Dict[str, Any]]] = None
    proposed_obligations: Optional[List[Dict[str, Any]]] = None
    proposed_authorizations: Optional[List[Dict[str, Any]]] = None
    
    # Human review results
    approved_entities: Optional[List[Dict[str, Any]]] = None
    approved_tasks: Optional[List[Dict[str, Any]]] = None
    human_corrections: Optional[Dict[str, Any]] = None
    
    # Database operations
    created_records: Optional[Dict[str, List[str]]] = None

class DocumentProcessorService:
    """Service for processing documents and managing the workflow."""
    
    def __init__(self):
        """Initialize the document processor service."""
        self.ocr_service: Optional[OCRService] = None
        self.pdf_service: Optional[PDFService] = None
        self.vector_service: Optional[VectorStorageService] = None
        self.drive_service: Optional[GoogleDriveService] = None
        self.agent: Optional[Agent] = None
        self.slack_service: Optional[SlackService] = None
        logger.info("Document Processor Service initialized")

    async def initialize(
        self,
        ocr_service: OCRService,
        pdf_service: PDFService,
        vector_service: VectorStorageService,
        drive_service: GoogleDriveService,
        agent: Agent,
        slack_service: SlackService
    ):
        """Initialize the service with required dependencies."""
        self.ocr_service = ocr_service
        self.pdf_service = pdf_service
        self.vector_service = vector_service
        self.drive_service = drive_service
        self.agent = agent
        self.slack_service = slack_service
        logger.info("Document Processor Service initialized with all dependencies")

    async def process_document(self, file_id: str) -> Dict[str, Any]:
        """Process a document through the workflow.
        
        Simple workflow:
        1. Download and extract text
        2. Send for review
        3. Store result if approved
        """
        temp_file_path = None
        try:
            # Get file metadata
            file_metadata = await self.drive_service.get_file_metadata(file_id)
            if not file_metadata:
                raise ValueError(f"Could not get metadata for file: {file_id}")

            file_name = file_metadata["name"]
            mime_type = file_metadata["mimeType"]
            logger.info(f"Processing {file_name} (Type: {mime_type})")

            # Download file
            temp_file_path = await self.drive_service.download_file_to_temp(file_id)
            if not temp_file_path:
                raise ValueError(f"Could not download file: {file_id}")

            # Extract text based on file type
            extracted_text = None
            extraction_method = None

            if mime_type == "application/pdf":
                # Try PDF service first
                pdf_result = await self.pdf_service.extract_text(temp_file_path)
                if pdf_result["success"]:
                    extracted_text = pdf_result["text"]
                    extraction_method = f"pdf_{pdf_result.get('parser_used', 'unknown')}"

            # Fallback to OCR if needed
            if not extracted_text:
                ocr_result = await self.ocr_service.process_document(
                    file_path=temp_file_path,
                    mime_type=mime_type
                )
                if not ocr_result["success"]:
                    raise ValueError(f"Text extraction failed: {ocr_result.get('error')}")
                
                extracted_text = ocr_result["text"]
                extraction_method = "ocr"

            # Prepare document info
            document_info = {
                "file_id": file_id,
                "file_name": file_name,
                "text": extracted_text,
                "extraction_method": extraction_method,
                "processed_at": datetime.now().isoformat()
            }

            # Add status to document_info
            document_info["status"] = "pending_approval"
            
            return {
                "success": True,
                "document_info": document_info
            }

        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                    logger.debug(f"Cleaned up temporary file: {temp_file_path}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file: {str(e)}")

    async def _send_for_review(self, document_info: Dict[str, Any]) -> Dict[str, Any]:
        """Send document for review via Slack."""
        try:
            # Create a simple message with document preview
            preview = document_info["text"][:500] + "..." if len(document_info["text"]) > 500 else document_info["text"]
            message = (
                f"*New Document for Review*\n"
                f"*File:* {document_info['file_name']}\n"
                f"*Extraction:* {document_info['extraction_method']}\n\n"
                f"*Preview:*\n```{preview}```"
            )

            # Send to Slack with approve/reject buttons
            result = await self.slack_service.send_message(
                text=message,
                blocks=[
                    {"type": "section", "text": {"type": "mrkdwn", "text": message}},
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "Approve"},
                                "style": "primary",
                                "value": f"approve_{document_info['file_id']}"
                            },
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "Reject"},
                                "style": "danger",
                                "value": f"reject_{document_info['file_id']}"
                            }
                        ]
                    }
                ]
            )

            return result

        except Exception as e:
            logger.error(f"Error sending for review: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def handle_approval(
        self,
        file_id: str,
        approved: bool,
        approver: str,
        comments: Optional[str] = None
    ) -> Dict[str, Any]:
        """Handle the approval/rejection of a document."""
        try:
            if approved:
                # Store the approved document
                await self.vector_service.store_document(
                    file_id=file_id,
                    metadata={
                        "status": "approved",
                        "approver": approver,
                        "approved_at": datetime.now().isoformat(),
                        "comments": comments
                    }
                )
                
                logger.info(f"Document {file_id} approved by {approver}")
                return {
                    "success": True,
                    "status": "approved",
                    "approver": approver
                }
            else:
                logger.info(f"Document {file_id} rejected by {approver}")
                return {
                    "success": True,
                    "status": "rejected",
                    "approver": approver
                }

        except Exception as e:
            logger.error(f"Error handling approval: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _extract_tasks(self, text: str, extracted_fields: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract tasks from document text and structured fields.
        
        Args:
            text (str): Raw document text
            extracted_fields (Dict[str, Any]): Previously extracted structured fields
            
        Returns:
            List[Dict[str, Any]]: List of structured tasks
        """
        tasks = []
        try:
            # First, check if we have tasks in extracted_fields
            if extracted_fields and "task" in extracted_fields:
                task_data = extracted_fields["task"]
                if isinstance(task_data, dict):
                    tasks.append({
                        "id": f"TASK_{len(tasks) + 1}",
                        "description": task_data.get("description", ""),
                        "type": task_data.get("type", ""),
                        "entity": task_data.get("entity", ""),
                        "due_date": task_data.get("due_date", ""),
                        "frequency": task_data.get("frequency", ""),
                        "status": task_data.get("status", "Pending"),
                        "priority": task_data.get("priority", "Medium"),
                        "notes": task_data.get("notes", "")
                    })
            
            # Then look for task-related patterns in text
            lines = text.split('\n')
            current_task = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Look for task indicators
                task_indicators = ["TODO:", "Task:", "Action Item:", "Required:", "Must:", "Should:", "Needs to:"]
                if any(indicator in line for indicator in task_indicators) or (
                    any(word in line.upper() for word in ["COMPLETE", "SUBMIT", "REVIEW", "PREPARE", "UPDATE", "NOTIFY"]) and
                    "BY" in line.upper()
                ):
                    # Start new task
                    if current_task:
                        tasks.append(current_task)
                    
                    current_task = {
                        "id": f"TASK_{len(tasks) + 1}",
                        "description": line,
                        "type": "",
                        "entity": "",
                        "due_date": "",
                        "frequency": "",
                        "status": "Pending",
                        "priority": "Medium",
                        "notes": ""
                    }
                    
                    # Try to extract due date from the same line
                    date_indicators = ["by", "due", "before", "until", "deadline"]
                    for indicator in date_indicators:
                        if indicator in line.lower():
                            parts = line.lower().split(indicator)
                            if len(parts) > 1:
                                current_task["due_date"] = parts[1].strip()
                
                # Look for task attributes in subsequent lines
                elif current_task:
                    line_lower = line.lower()
                    if "priority:" in line_lower:
                        current_task["priority"] = line.split(":", 1)[1].strip()
                    elif "type:" in line_lower:
                        current_task["type"] = line.split(":", 1)[1].strip()
                    elif "status:" in line_lower:
                        current_task["status"] = line.split(":", 1)[1].strip()
                    elif "frequency:" in line_lower:
                        current_task["frequency"] = line.split(":", 1)[1].strip()
                    elif "notes:" in line_lower:
                        current_task["notes"] = line.split(":", 1)[1].strip()
                    elif "entity:" in line_lower:
                        current_task["entity"] = line.split(":", 1)[1].strip()
                    else:
                        # Append to description if it seems to be continuation
                        if line[0].islower() or line.startswith("  "):
                            current_task["description"] += " " + line
            
            # Add last task if exists
            if current_task:
                tasks.append(current_task)
            
            # Also check for obligations and convert them to tasks
            if extracted_fields and "obligation" in extracted_fields:
                obligation = extracted_fields["obligation"]
                if isinstance(obligation, dict) and obligation.get("description"):
                    tasks.append({
                        "id": f"TASK_{len(tasks) + 1}",
                        "description": obligation["description"],
                        "type": "Obligation",
                        "entity": obligation.get("related_entity", ""),
                        "due_date": obligation.get("trigger_date", ""),
                        "frequency": obligation.get("frequency", ""),
                        "status": "Pending",
                        "priority": "High",  # Obligations are typically high priority
                        "notes": f"Reminder Lead Time: {obligation.get('reminder_lead_time', 'Not specified')}"
                    })
            
            # Deduplicate tasks
            unique_tasks = []
            seen_descriptions = set()
            for task in tasks:
                desc = task["description"].lower().strip()
                if desc not in seen_descriptions:
                    seen_descriptions.add(desc)
                    unique_tasks.append(task)
            
            return unique_tasks
            
        except Exception as e:
            logger.error(f"Error extracting tasks: {str(e)}")
            return []

    def _extract_entity_from_filename(self, file_name: str) -> str:
        """Extract entity name from filename using common patterns."""
        # Remove file extension and version markers
        clean_name = file_name.replace('.pdf', '').replace('_vF', '').strip()
        
        # Pattern 1: Company Q[X] Letter
        if 'Letter' in clean_name and any(q in clean_name for q in ['Q1', 'Q2', 'Q3', 'Q4']):
            parts = clean_name.split()
            if len(parts) > 0:
                return parts[0]  # Return company name (e.g., "Strobe")
        
        # Pattern 2: Contrato Mutuo [Name]
        if 'Contrato Mutuo' in clean_name:
            parts = clean_name.split('Contrato Mutuo')
            if len(parts) > 1:
                name_part = parts[1].split('MX-')[0].strip()  # Get name before contract number
                return name_part
        
        return "Unknown"

    def _simplify_entity_name(self, entity_name: str, file_name: str = None) -> str:
        """
        Simplify and standardize entity names to max 2 words.
        Example: 'Apple Inc.' -> 'Apple', 'Bank of America Corp' -> 'Bank America'
        """
        # First try to extract from filename if available
        if file_name:
            filename_entity = self._extract_entity_from_filename(file_name)
            if filename_entity != "Unknown":
                return filename_entity
        
        if not entity_name:
            return "Unknown"
            
        # Remove common business suffixes
        suffixes = [" Inc", " Corp", " LLC", " Ltd", " Limited", " Corporation", " Company", " Co"]
        clean_name = entity_name
        for suffix in suffixes:
            clean_name = clean_name.replace(suffix, "")
            clean_name = clean_name.replace(suffix.lower(), "")
            
        # Split and take first two words
        words = clean_name.strip().split()
        if len(words) > 2:
            words = words[:2]
        
        return " ".join(words)

    def _extract_document_title(self, file_name: str, text: str) -> str:
        """
        Extract meaningful document title from content and filename.
        Example: "Strobe Q1 2025 Letter_vF.pdf" -> "Strobe Q1 2025 Quarterly Letter"
        """
        # Start with cleaning up filename
        clean_name = file_name.replace('.pdf', '').replace('_vF', '').replace('_', ' ').strip()
        
        # Handle quarterly letters
        if any(q in clean_name for q in ['Q1', 'Q2', 'Q3', 'Q4']):
            if 'Letter' in clean_name:
                return clean_name.replace('Letter', 'Quarterly Letter')
        
        # Handle contracts and agreements
        if 'Contrato' in clean_name or 'Agreement' in clean_name:
            return clean_name
        
        # Only if filename is not meaningful, try document content
        if len(clean_name) < 10:
            first_lines = text.split('\n')[:5]
            for line in first_lines:
                line = line.strip()
                if len(line) > 10 and not line.startswith(('http', 'www', 'Page', 'Source')):
                    return line
        
        return clean_name

    async def _generate_document_summary(self, text: str, extracted_fields: Dict[str, Any]) -> str:
        """
        Generate a 2-3 sentence summary focusing on key information.
        Include: dates, performance, amounts, parties involved if relevant.
        """
        try:
            # Use agent to generate concise summary
            if self.agent:
                summary_prompt = (
                    "Generate a 2-3 sentence summary of this document. "
                    "Include relevant dates, performance metrics, amounts, and parties involved. "
                    "Focus on the main purpose and key information."
                )
                summary = await self.agent.generate_summary(text, summary_prompt)
                if summary:
                    return summary
            
            # Fallback to basic summary if agent fails
            first_100_words = ' '.join(text.split()[:100])
            return f"Document contains {len(text.split())} words. First 100 words: {first_100_words}..."
            
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return "Summary generation failed"

    def _extract_simple_task(self, text: str, extracted_fields: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """
        Extract simple task based on document content.
        Only return a task if there's a clear action required.
        """
        # Look for explicit requests or required actions
        request_indicators = [
            "please provide", "please submit", "required to submit",
            "need by", "due by", "deadline", "respond by",
            "action required", "action needed", "please review"
        ]
        
        text_lower = text.lower()
        
        # 1. Check for specific answer/action requested
        for indicator in request_indicators:
            if indicator in text_lower:
                # Find the sentence containing the request
                sentences = text.split('.')
                for sentence in sentences:
                    if indicator in sentence.lower():
                        return {
                            "type": "Action Required",
                            "description": sentence.strip()
                        }
        
        # 2. Check for date-sensitive actions
        date_indicators = ["by", "before", "until", "deadline"]
        for indicator in date_indicators:
            if indicator in text_lower:
                sentences = text.split('.')
                for sentence in sentences:
                    if indicator in sentence.lower() and any(d in sentence for d in ["202", "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]):
                        return {
                            "type": "Time Sensitive",
                            "description": sentence.strip()
                        }
        
        # 3. Check for information/document requests
        info_indicators = ["please send", "please provide", "submit", "forward"]
        for indicator in info_indicators:
            if indicator in text_lower:
                sentences = text.split('.')
                for sentence in sentences:
                    if indicator in sentence.lower():
                        return {
                            "type": "Information Request",
                            "description": sentence.strip()
                        }
        
        # No clear task found
        return None

    async def approve_document(self, file_id: str, approved_entity: str, human_corrections: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Handle human approval and execute final actions.
        This method is called ONLY after human approval via Slack.
        
        Args:
            file_id (str): Google Drive file ID
            approved_entity (str): Human-approved entity name
            human_corrections (Dict): Any corrections from human reviewer
            
        Returns:
            Dict[str, Any]: Final processing result
        """
        try:
            logger.info(f"APPROVAL RECEIVED - Processing approval for file: {file_id}")
            logger.info(f"APPROVAL RECEIVED - Approved entity: {approved_entity}")
            
            # Get file metadata again
            file_metadata = await self.drive_service.get_file_metadata(file_id)
            file_name = file_metadata.get('name', 'Unknown file')
            
            # STEP A: Create or match folder based on APPROVED entity
            try:
                folder_result = await self.drive_service.create_or_match_folder(approved_entity)
                if not folder_result or not folder_result.get("folder_id"):
                    raise ValueError("Failed to create/match folder")
                logger.info(f"APPROVAL ACTION - Created/matched folder for {approved_entity}")
            except Exception as e:
                error_msg = f"APPROVAL FAILED - Folder operation: {str(e)}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "file_id": file_id,
                    "file_name": file_name,
                    "entity_name": approved_entity
                }
            
            # STEP B: Move file to approved folder
            try:
                move_result = await self.drive_service.move_file_to_folder(
                    file_id=file_id,
                    folder_id=folder_result["folder_id"]
                )
                if not move_result or not move_result.get("id"):
                    raise ValueError("Failed to move file")
                logger.info(f"APPROVAL ACTION - Successfully moved file to {approved_entity} folder")
            except Exception as e:
                error_msg = f"APPROVAL FAILED - File move: {str(e)}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "file_id": file_id,
                    "file_name": file_name,
                    "folder_id": folder_result["folder_id"]
                }
            
            # STEP C: Store in vector database (now that it's approved)
            try:
                # Re-extract text for vector storage
                ocr_result = await self.ocr_service.extract_text(file_id)
                if ocr_result.get("success"):
                    extracted_text = ocr_result.get("text", "")
                    
                    document_info = {
                        "file_name": file_name,
                        "entity_name": approved_entity,
                        "processing_time": datetime.utcnow().isoformat(),
                        "file_metadata": file_metadata,
                        "status": "approved_and_processed",
                        "human_corrections": human_corrections or {}
                    }
                    
                    await self.vector_service.store_document(
                        document_id=file_id,
                        content=extracted_text,
                        metadata=document_info
                    )
                    logger.info("APPROVAL ACTION - Successfully stored document in vector database")
            except Exception as e:
                error_msg = f"APPROVAL WARNING - Vector storage: {str(e)}"
                logger.warning(error_msg)
                # Continue as this is not critical
            
            # STEP D: Send confirmation
            if self.slack_service:
                try:
                    message = (
                        f"✅ *DOCUMENT APPROVED & PROCESSED*\n\n"
                        f"📄 *Document:* {file_name}\n"
                        f"🏢 *Final Entity:* {approved_entity}\n"
                        f"📁 *Moved to Folder:* {approved_entity}\n"
                        f"💾 *Vector Storage:* ✅ Complete\n"
                        f"📅 *Completed:* {datetime.utcnow().isoformat()}\n\n"
                        f"*🔗 Drive Link:* https://drive.google.com/file/d/{file_id}"
                    )
                    
                    await self.slack_service.send_review_request(message)
                    logger.info("APPROVAL ACTION - Sent completion confirmation to Slack")
                except Exception as e:
                    logger.error(f"APPROVAL WARNING - Slack confirmation: {str(e)}")
            
            return {
                "success": True,
                "status": "approved_and_processed",
                "message": f"Document approved and processed: {file_name}",
                "entity_name": approved_entity,
                "folder_id": folder_result["folder_id"],
                "final_actions": [
                    "Folder created/matched",
                    "File moved to folder",
                    "Stored in vector database",
                    "Confirmation sent"
                ]
            }
            
        except Exception as e:
            error_msg = f"APPROVAL FAILED - Error: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "file_id": file_id
            }

    async def wait_for_approval(self, document_info: Dict[str, Any]) -> Dict[str, Any]:
        """Wait for human approval and process the response.
        
        Args:
            document_info: Document information including file_id, entity_name, etc.
            
        Returns:
            Dict containing the approval result
        """
        try:
            # Format and send review message
            review_message = self._format_review_message(document_info)
            slack_result = await self.slack_service.send_review_request(review_message)
            
            if not slack_result.get("ok"):
                raise ValueError(f"Failed to send Slack message: {slack_result.get('error')}")
            
            # Wait for human response
            channel = slack_result["channel"]
            thread_ts = slack_result["ts"]
            
            logger.info("Waiting for human approval...")
            response = await self.slack_service.wait_for_response(
                channel=channel,
                thread_ts=thread_ts
            )
            
            if not response:
                logger.warning("No response received within timeout period")
                return {
                    "success": True,
                    "status": "pending_approval",
                    "document_info": document_info,
                    "message": "Waiting for human approval"
                }
            
            # Process the approval/correction
            if response["action"] == "approve":
                # Call handler_vector to process approval
                approval_result = await self.handler_vector.handle_approval(
                    file_id=document_info["file_id"],
                    approved_entity=response["entity_name"] or document_info["entity_name"],
                    human_corrections=response.get("corrections")
                )
                
                if approval_result["success"]:
                    document_info["status"] = "approved_and_processed"
                    logger.info("Document approved and processed")
                    return {
                        "success": True,
                        "status": "approved_and_processed",
                        "document_info": document_info,
                        "approval_result": approval_result
                    }
                else:
                    logger.error(f"Failed to process approval: {approval_result.get('error')}")
                    document_info["status"] = "approval_failed"
                    return {
                        "success": False,
                        "status": "approval_failed",
                        "document_info": document_info,
                        "error": approval_result.get("error")
                    }
            
            elif response["action"] == "correct":
                # Update document info with corrections
                document_info.update(response.get("corrections", {}))
                document_info["status"] = "corrections_received"
                logger.info("Received corrections from human review")
                return {
                    "success": True,
                    "status": "corrections_received",
                    "document_info": document_info,
                    "corrections": response.get("corrections")
                }
            
            return {
                "success": True,
                "status": "unknown_response",
                "document_info": document_info,
                "message": "Received unknown response type"
            }
            
        except Exception as e:
            logger.error(f"Error in approval workflow: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "document_info": document_info
            }

    def _format_review_message(self, document_info: Dict[str, Any]) -> str:
        """Format document info into a Slack review request message.
        
        Args:
            document_info: Document information including title, entity, summary etc.
            
        Returns:
            Formatted message string for Slack
        """
        message = (
            f"🔍 *DOCUMENT REVIEW REQUIRED*\n\n"
            f"📄 *Document Title:* {document_info['document_title']}\n"
            f"🏢 *Entity:* {document_info['entity_name']}\n"
            f"📅 *Date:* {document_info['processing_time']}\n"
            f"📎 *Type:* {document_info['mime_type']}\n\n"
            f"*📝 Summary:*\n{document_info['summary']}\n\n"
            f"*🔗 Drive Link:* https://drive.google.com/file/d/{document_info['file_id']}\n\n"
            f"⚠️ **Please review and approve/reject/correct the analysis.**\n"
            f"- Type 'approve' or '✅' to approve as is\n"
            f"- Type 'approve as ENTITY_NAME' to approve with a different entity name\n"
            f"- Type 'correct entity to ENTITY_NAME' to request corrections"
        )
        return message

class DocumentProcessor:
    """Service for processing and storing documents with vector search capabilities."""
    
    def __init__(
        self,
        persist_directory: str = "chroma_db",
        collection_name: str = "documents"
    ):
        """Initialize the document processor.
        
        Args:
            persist_directory (str): Directory to persist the vector database
            collection_name (str): Name of the collection to store documents
        """
        self.vector_store = VectorStorageService()
        self.embedding_service = EmbeddingService()
        
    async def process_and_store_document(
        self,
        document: Dict[str, Any],
        chunk_size: int = 1000,
        overlap: int = 200
    ) -> Dict[str, Any]:
        """Process a document and store it in the vector database.
        
        Args:
            document (Dict[str, Any]): Document to process
            chunk_size (int): Size of text chunks
            overlap (int): Overlap between chunks
            
        Returns:
            Dict[str, Any]: Result of the operation
        """
        try:
            # Extract text from document
            text = document.get("text", "")
            if not text:
                raise ValueError("Document must contain 'text' field")
            
            # Split text into chunks
            chunks = self._split_text_into_chunks(text, chunk_size, overlap)
            
            # Generate embeddings for chunks
            chunk_documents = []
            chunk_embeddings = []
            chunk_metadata = []
            
            for i, chunk in enumerate(chunks):
                # Generate embedding
                embedding_result = await self.embedding_service.generate_embeddings(chunk)
                if not embedding_result["success"]:
                    raise Exception(f"Failed to generate embedding for chunk {i}: {embedding_result.get('error')}")
                
                # Prepare chunk data
                chunk_documents.append({"text": chunk})
                chunk_embeddings.append(embedding_result["embeddings"])
                chunk_metadata.append({
                    "document_id": document.get("id", "unknown"),
                    "title": document.get("title", "Untitled"),
                    "chunk_index": i,
                    "source": document.get("source", "unknown")
                })
            
            # Store chunks in vector database
            store_result = await self.vector_store.add_documents(
                documents=chunk_documents,
                embeddings=chunk_embeddings,
                metadata=chunk_metadata
            )
            
            if not store_result["success"]:
                raise Exception(f"Failed to store document chunks: {store_result.get('error')}")
            
            return {
                "success": True,
                "message": f"Processed and stored document with {len(chunks)} chunks",
                "chunk_count": len(chunks),
                "document_id": document.get("id")
            }
            
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def search_documents(
        self,
        query: str,
        top_k: int = 3,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Search for documents similar to the query.
        
        Args:
            query (str): Search query
            top_k (int): Number of results to return
            filters (Optional[Dict[str, Any]]): Filter conditions
            
        Returns:
            Dict[str, Any]: Search results
        """
        try:
            # Generate query embedding
            query_result = await self.embedding_service.generate_embeddings(query)
            if not query_result["success"]:
                raise Exception(f"Failed to generate query embedding: {query_result.get('error')}")
            
            # Search vector store
            search_result = await self.vector_store.search_similar(
                query_embedding=query_result["embeddings"],
                top_k=top_k,
                where=filters
            )
            
            if not search_result["success"]:
                raise Exception(f"Search failed: {search_result.get('error')}")
            
            return {
                "success": True,
                "query": query,
                "results": search_result["results"],
                "total_results": search_result["total_results"]
            }
            
        except Exception as e:
            logger.error(f"Error searching documents: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _split_text_into_chunks(
        self,
        text: str,
        chunk_size: int,
        overlap: int
    ) -> List[str]:
        """Split text into overlapping chunks.
        
        Args:
            text (str): Text to split
            chunk_size (int): Size of each chunk
            overlap (int): Overlap between chunks
            
        Returns:
            List[str]: List of text chunks
        """
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = start + chunk_size
            if end > text_length:
                end = text_length
            
            chunk = text[start:end]
            chunks.append(chunk)
            
            start = end - overlap
        
        return chunks