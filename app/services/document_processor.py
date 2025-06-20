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
import json

logger = logging.getLogger(__name__)

class DocumentProcessorService:
    """Service for processing documents and managing the processing workflow."""
    
    def __init__(self):
        """Initialize the document processor service."""
        self.ocr_service: Optional[OCRService] = None
        self.vector_service: Optional[VectorStorageService] = None
        self.drive_service: Optional[GoogleDriveService] = None
        self.agent: Optional[Agent] = None
        self.slack_service: Optional[SlackService] = None
        logger.info("Document Processor Service initialized")

    async def initialize(
        self,
        ocr_service: OCRService,
        vector_service: VectorStorageService,
        drive_service: GoogleDriveService,
        agent: Agent,
        slack_service: SlackService
    ):
        """Initialize the service with required dependencies."""
        self.ocr_service = ocr_service
        self.vector_service = vector_service
        self.drive_service = drive_service
        self.agent = agent
        self.slack_service = slack_service
        logger.info("Document Processor Service initialized with dependencies")

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

    async def process_document(self, file_id: str) -> Dict[str, Any]:
        """
        Process a document through the complete workflow.
        IMPORTANT: NO files are moved until human approval is received via Slack.
        
        Args:
            file_id (str): Google Drive file ID
            
        Returns:
            Dict[str, Any]: Processing result with extracted data for human review
        """
        try:
            logger.info(f"Starting document processing for file: {file_id}")
            
            # Validate dependencies
            missing_services = []
            if not self.ocr_service:
                missing_services.append("OCR Service")
            if not self.vector_service:
                missing_services.append("Vector Storage Service")
            if not self.drive_service:
                missing_services.append("Drive Service")
            if not self.agent:
                missing_services.append("Agent")
            
            if missing_services:
                error_msg = f"Required services not initialized: {', '.join(missing_services)}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "missing_services": missing_services
                }
            
            # STEP 1: Get file metadata
            try:
                file_metadata = await self.drive_service.get_file_metadata(file_id)
                if not file_metadata:
                    raise ValueError("No metadata returned for file")
                
                file_name = file_metadata.get('name', 'Unknown file')
                mime_type = file_metadata.get('mimeType', '')
                logger.info(f"STEP 1 - File Metadata: {file_name} (Type: {mime_type})")
            except Exception as e:
                error_msg = f"STEP 1 FAILED - File metadata: {str(e)}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "file_id": file_id
                }
            
            # STEP 2: Download/Export file content
            try:
                if "google-apps" in mime_type:
                    logger.info(f"STEP 2 - Exporting Google Workspace file: {file_name}")
                    file_content = await self.drive_service.export_file(file_id, "application/pdf")
                    logger.info("STEP 2 - Successfully exported Google Workspace file to PDF")
                else:
                    logger.info(f"STEP 2 - Downloading regular file: {file_name}")
                    file_content = await self.drive_service.download_file(file_id)
                    logger.info("STEP 2 - Successfully downloaded file")
            except Exception as e:
                error_msg = f"STEP 2 FAILED - File processing: {str(e)}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "file_id": file_id,
                    "file_name": file_name,
                    "mime_type": mime_type
                }
            
            # STEP 3: Extract text and structured data
            logger.info("STEP 3 - Processing document with OCR...")
            try:
                ocr_result = await self.ocr_service.process_document(file_id)
                
                if not ocr_result.get("success"):
                    logger.error(f"STEP 3 FAILED - OCR processing: {ocr_result.get('error')}")
                    return {
                        "success": False,
                        "error": f"STEP 3 FAILED - OCR processing: {ocr_result.get('error')}",
                        "file_id": file_id
                    }
                
                # Parse OCR result if needed
                if isinstance(ocr_result, str):
                    try:
                        ocr_result = json.loads(ocr_result)
                    except json.JSONDecodeError as e:
                        logger.error(f"STEP 3 FAILED - Parse OCR result: {str(e)}")
                        return {
                            "success": False,
                            "error": f"STEP 3 FAILED - Parse OCR result: {str(e)}",
                            "file_id": file_id
                        }
                
                logger.info("STEP 3 - OCR processing completed successfully")
            except Exception as e:
                logger.error(f"STEP 3 FAILED - OCR processing: {str(e)}")
                return {
                    "success": False,
                    "error": f"STEP 3 FAILED - OCR processing: {str(e)}",
                    "file_id": file_id
                }
            
            # STEP 4: Extract and structure information
            extracted_text = ocr_result.get("data", {}).get("raw_text", "")
            extracted_fields = ocr_result.get("data", {}).get("extracted_fields", {})
            
            # Get and simplify entity name
            raw_entity_name = extracted_fields.get("entity", {}).get("name", "")
            entity_name = self._simplify_entity_name(raw_entity_name, file_name)
            
            # Extract meaningful document title
            document_title = self._extract_document_title(file_name, extracted_text)
            
            # Generate document summary
            document_summary = await self._generate_document_summary(extracted_text, extracted_fields)
            
            # Extract simple task (if any)
            task = self._extract_simple_task(extracted_text, extracted_fields)
            
            # Update document info
            document_info = {
                "file_name": file_name,
                "document_title": document_title,
                "file_id": file_id,
                "entity_name": entity_name,
                "processing_time": datetime.utcnow().isoformat(),
                "summary": document_summary,
                "task": task,
                "file_metadata": file_metadata,
                "mime_type": mime_type,
                "status": "pending_approval"
            }
            
            # STEP 6: Send for human approval (NO file moving yet!)
            if self.slack_service:
                try:
                    # Format approval request message
                    message = (
                        f"🔍 *DOCUMENT REVIEW REQUIRED*\n\n"
                        f"📄 *Document Title:* {document_title}\n"
                        f"🏢 *Entity:* {entity_name}\n"
                        f"📅 *Date:* {document_info['processing_time']}\n"
                        f"📎 *Type:* {mime_type}\n\n"
                        f"*📝 Summary:*\n{document_summary}\n\n"
                    )
                    
                    if task:
                        message += (
                            f"*⚡ Required Action:*\n"
                            f"Type: {task['type']}\n"
                            f"Description: {task['description']}\n\n"
                        )
                    
                    message += (
                        f"*🔗 Drive Link:* https://drive.google.com/file/d/{file_id}\n\n"
                        f"⚠️ **NO FILES HAVE BEEN MOVED YET**\n"
                        f"Please review and approve/reject/correct the analysis before any actions are taken."
                    )
                    
                    await self.slack_service.send_message(message)
                    logger.info("STEP 6 - Successfully sent approval request to Slack")
                except Exception as e:
                    logger.error(f"STEP 6 FAILED - Slack notification: {str(e)}")
                    # Continue as this is not critical for processing
            
            # STEP 5: Generate review tasks for human
            try:
                review_tasks = await self.agent.plan_review_tasks(document_info)
                if not review_tasks:
                    logger.warning("STEP 5 - No review tasks generated")
                    review_tasks = ["Review document classification and entity identification"]
                logger.info(f"STEP 5 - Generated {len(review_tasks)} review tasks")
            except Exception as e:
                error_msg = f"STEP 5 FAILED - Plan review tasks: {str(e)}"
                logger.error(error_msg)
                review_tasks = [f"Error: {error_msg}", "Manual review required"]
            
            # IMPORTANT: DO NOT move files or store in vector DB until approval
            logger.info("STEP 7 - WAITING FOR HUMAN APPROVAL - No actions taken until approved")
            
            return {
                "success": True,
                "status": "pending_approval",
                "message": f"Document processed and sent for review: {file_name}",
                "entity_name": entity_name,
                "review_tasks": review_tasks,
                "document_info": document_info,
                "next_action": "awaiting_human_approval"
            }
            
        except Exception as e:
            error_msg = f"Error processing document: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "file_id": file_id
            }

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