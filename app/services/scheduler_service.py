# gabriel-agent/app/services/scheduler_service.py

import asyncio
import logging
from datetime import datetime, timedelta
from ..core.config import get_settings
from .google_drive import GoogleDriveService
from .agent import Agent
from .slack_service import SlackService
from .file_discovery_service import FileDiscoveryService
from .document_processor import DocumentProcessorService
import fitz
from typing import List, Dict, Any, Optional
from googleapiclient.discovery import build
import json

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class SchedulerService:
    """Service for scheduling and triggering document scans."""
    
    def __init__(self):
        """Initialize the scheduler service."""
        self.settings = get_settings()
        self.drive_service = None  # Will be injected from main.py
        self.agent: Optional[Agent] = None
        self.slack_service: Optional[SlackService] = None
        self.file_discovery: Optional[FileDiscoveryService] = None
        self.document_processor = None  # Will be injected from main.py
        self.agent_coordinator = None  # Will be injected from main.py
        self.scan_interval = self.settings.SCHEDULER_SCAN_INTERVAL
        self.is_running = False
        self.task: Optional[asyncio.Task] = None
        self.last_scan_time = None
        self.temp_dir = get_settings().TEMP_DIR
        logger.info("Scheduler Service initialized")

    async def initialize(
        self,
        agent: Agent,
        slack_service: SlackService,
        file_discovery: FileDiscoveryService,
        document_processor: 'DocumentProcessorService' = None,
        drive_service: 'GoogleDriveService' = None,
        agent_coordinator = None
    ):
        """Initialize the service with required dependencies."""
        self.agent = agent
        self.slack_service = slack_service
        self.file_discovery = file_discovery
        self.agent_coordinator = agent_coordinator
        
        # Use provided document processor or create new one
        if document_processor:
            self.document_processor = document_processor
            logger.info("Using provided document processor")
        else:
            # Initialize the document processor with required services
            from .ocr_service import OCRService
            from .pdf_service import PDFService
            from .vector_storage_service import VectorStorageService
            
            try:
                ocr_service = OCRService()
                pdf_service = PDFService()
                vector_service = VectorStorageService()
                
                await self.document_processor.initialize(
                    ocr_service=ocr_service,
                    pdf_service=pdf_service,
                    vector_service=vector_service,
                    drive_service=self.drive_service,
                    agent=agent,
                    slack_service=slack_service
                )
                logger.info("Document processor initialized with all services")
            except Exception as e:
                logger.error(f"Failed to initialize document processor: {e}")
                # Continue with limited functionality
        
        # Use provided drive service (required for authentication)
        if drive_service:
            self.drive_service = drive_service
            logger.info("Using provided authenticated Google Drive service")
        else:
            logger.error("No Google Drive service provided - folder scanning will fail")
        
        logger.info("Scheduler Service initialized with dependencies")

    async def _process_via_agent_coordinator(self, file_id: str, file_data: dict) -> dict:
        """Process document using the proper Agent Coordinator workflow"""
        try:
            file_name = file_data["name"]
            logger.info(f"Processing {file_name} via Agent Coordinator workflow...")
            
            # Use the Agent Coordinator's document processing workflow
            result = await self.agent_coordinator.process_document_workflow({
                "file_id": file_id,
                "file_name": file_name,
                "file_data": file_data,
                "source": "SCHEDULER_SERVICE"
            })
            
            if result.get("status") == "success":
                logger.info(f"Agent Coordinator workflow completed for: {file_name}")
                return {"success": True, "workflow_result": result}
            else:
                logger.error(f"Agent Coordinator workflow failed for {file_name}: {result}")
                return {"success": False, "error": result.get("message", "Unknown error")}
                
        except Exception as e:
            logger.error(f"Error in Agent Coordinator workflow for {file_name}: {e}")
            return {"success": False, "error": str(e)}

    async def start(self):
        """Start the scheduler."""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        logger.info("Starting scheduler service")
        self.is_running = True
        self.task = asyncio.create_task(self._run_scheduler())
        logger.info("Scheduler started")

    async def stop(self):
        """Stop the scheduler."""
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return
        
        logger.info("Stopping scheduler service")
        self.is_running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.task = None
        logger.info("Scheduler stopped")

    async def _run_scheduler(self):
        """Run the scheduler loop."""
        while self.is_running:
            try:
                logger.debug("Running scheduled scan")
                await self._run_scan()
                self.last_scan_time = datetime.utcnow()
                logger.debug(f"Scan completed at {self.last_scan_time}")
                
                # Wait for next scan interval
                await asyncio.sleep(self.scan_interval)
                
            except asyncio.CancelledError:
                logger.info("Scheduler task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {str(e)}")
                # Wait a bit before retrying on error
                await asyncio.sleep(60)

    async def _run_scan(self):
        """Run document scanning and processing"""
        try:
            logger.debug("Running scheduled scan")
            logger.info("Starting document scan")
            
            # Get files from Google Drive
            files = await self.drive_service.get_folder_contents()
            
            if not files:
                logger.info("No files found in folder")
                return
            
            logger.debug(f"Found {len(files)} files in folder")
            
            # Process each file
            processed_count = 0
            for file_data in files:
                file_id = file_data["id"]
                file_name = file_data["name"]
                
                logger.debug(f"Processing file: {file_name}")
                
                try:
                    # 🔥 NEW: Check if file already processed
                    if await self._is_file_already_processed(file_id):
                        logger.debug(f"File {file_name} already processed, skipping")
                        continue
                    
                    # Process the document through Agent Coordinator workflow
                    if self.agent_coordinator:
                        result = await self._process_via_agent_coordinator(file_id, file_data)
                    else:
                        # Fallback to old workflow if coordinator not available
                        result = await self._process_document_complete_workflow(file_id, file_data)
                    
                    if result["success"]:
                        logger.info(f"Successfully processed: {file_name}")
                        processed_count += 1
                    else:
                        logger.error(f"Failed to process {file_name}: {result.get('error')}")
                        
                except Exception as e:
                    logger.error(f"Error processing {file_name}: {str(e)}")
                    continue
            
            logger.info(f"Document scan completed. {processed_count} new documents processed")
            
        except Exception as e:
            logger.error(f"Error during scheduled scan: {str(e)}")
            raise

    async def _is_file_already_processed(self, file_id: str) -> bool:
        """Check if a file has already been processed"""
        try:
            from ..core.database.service import get_database_service
            
            db_service = await get_database_service()
            
            # Query processed_files table
            query = "SELECT id FROM processed_files WHERE file_id = %s"
            result = await db_service.execute_query(query, (file_id,))
            
            return len(result) > 0
            
        except Exception as e:
            logger.warning(f"Error checking processed files: {e}")
            return False  # If we can't check, assume not processed

    async def _process_document_complete_workflow(self, file_id: str, file_data: dict) -> dict:
        """Complete document processing workflow - BUT WAIT for HDL approval before moving files"""
        try:
            file_name = file_data["name"]
            logger.info(f"Starting workflow for: {file_name}")
            
            # Step 1: Process document and get AI analysis
            result = await self.document_processor.process_document(file_id)
            
            if not result["success"]:
                return result
            
            analysis = result.get("analysis", {})
            entity_name = analysis.get("entity_name", "Unknown")
            
            # Step 2: Entity validation - Check if entity already exists
            entity_info = await self._check_existing_entity(entity_name)
            
            # Step 3: Send to HDL Agent for approval (FILE STAYS IN MASTER FOLDER)
            logger.info(f"Sending {file_name} to HDL Agent for entity approval...")
            
            hdl_request = {
                "type": "entity_approval",
                "entity_name": entity_name,
                "file_id": file_id,
                "file_name": file_name,
                "analysis": analysis,
                "existing_entity": entity_info,
                "message": self._format_entity_approval_message(entity_name, file_name, analysis, entity_info)
            }
            
            # Store workflow state for when approval comes back
            workflow_state = {
                "file_id": file_id,
                "file_name": file_name,
                "file_data": file_data,
                "analysis": analysis,
                "entity_name": entity_name,
                "existing_entity": entity_info,
                "status": "pending_hdl_approval"
            }
            
            # Store in processed files with pending status
            await self._store_pending_workflow(workflow_state)
            
            # Request HDL approval but DON'T move files yet
            if hasattr(self, 'agent_coordinator') and self.agent_coordinator:
                try:
                    hdl_response = await self.agent_coordinator.route_message(
                        "SCHEDULER_SERVICE", 
                        "HDL_AGENT", 
                        {"action": "request_review", "data": hdl_request}
                    )
                    
                    if hdl_response.get("status") == "success":
                        logger.info(f"✅ HDL approval requested for {file_name}")
                        logger.info(f"📁 File remains in master folder until approved")
                        
                        return {
                            "success": True,
                            "status": "pending_hdl_approval",
                            "message": f"File {file_name} awaiting human approval"
                        }
                    else:
                        logger.error(f"❌ Failed to request HDL approval: {hdl_response.get('message')}")
                        return {"success": False, "error": "HDL approval request failed"}
                        
                except Exception as e:
                    logger.error(f"❌ Error requesting HDL approval: {str(e)}")
                    return {"success": False, "error": f"HDL approval error: {str(e)}"}
            else:
                # Fallback: send via Slack service directly
                try:
                    await self.slack_service.send_message(hdl_request["message"])
                    logger.info(f"✅ HDL approval requested via Slack for {file_name}")
                    
                    return {
                        "success": True,
                        "status": "pending_hdl_approval",
                        "message": f"File {file_name} awaiting human approval"
                    }
                except Exception as e:
                    logger.error(f"❌ Error sending HDL request: {str(e)}")
                    return {"success": False, "error": f"Slack HDL error: {str(e)}"}
            
        except Exception as e:
            logger.error(f"Error in workflow: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _check_existing_entity(self, entity_name: str) -> dict:
        """Check if entity already exists in database"""
        try:
            from ..core.database.service import DatabaseService
            
            db_service = DatabaseService()
            
            # Check exact match first
            exact_query = "SELECT id, name, google_drive_folder_id FROM entities WHERE name = %s"
            exact_result = await db_service.execute_query(exact_query, (entity_name,))
            
            if exact_result:
                return {
                    "exists": True,
                    "match_type": "exact",
                    "entity_data": exact_result[0]
                }
            
            # TODO: Add fuzzy matching if needed
            # For now, just return "not found"
            return {
                "exists": False,
                "match_type": "none",
                "entity_data": None
            }
            
        except Exception as e:
            logger.error(f"Error checking existing entity: {str(e)}")
            return {"exists": False, "error": str(e)}

    async def _store_pending_workflow(self, workflow_state: dict):
        """Store workflow state while waiting for HDL approval"""
        try:
            from ..core.database.service import DatabaseService
            
            db_service = DatabaseService()
            
            # Create processed_files table if it doesn't exist
            create_table_query = """
            CREATE TABLE IF NOT EXISTS processed_files (
                id SERIAL PRIMARY KEY,
                file_id VARCHAR(255) UNIQUE NOT NULL,
                file_name VARCHAR(500) NOT NULL,
                entity_name VARCHAR(255),
                analysis JSONB,
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            
            await db_service.execute_command(create_table_query)
            
            # Store the workflow state
            insert_query = """
            INSERT INTO processed_files (file_id, file_name, entity_name, analysis, status)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (file_id) 
            DO UPDATE SET 
                file_name = EXCLUDED.file_name,
                entity_name = EXCLUDED.entity_name,
                analysis = EXCLUDED.analysis,
                status = EXCLUDED.status,
                updated_at = CURRENT_TIMESTAMP
            """
            
            await db_service.execute_command(
                insert_query,
                (
                    workflow_state["file_id"],
                    workflow_state["file_name"],
                    workflow_state["entity_name"],
                    json.dumps(workflow_state["analysis"]) if workflow_state.get("analysis") else None,
                    workflow_state["status"]
                )
            )
            
            logger.info(f"Stored pending workflow for file: {workflow_state['file_name']}")
            
        except Exception as e:
            logger.error(f"Error storing pending workflow: {str(e)}")
            # Don't raise - this shouldn't block the main workflow

    def _format_entity_approval_message(self, entity_name: str, file_name: str, analysis: dict, entity_info: dict) -> str:
        """Format the HDL approval message"""
        doc_type = analysis.get("document_type", "Document")
        confidence = analysis.get("entity_confidence", 0.0)
        
        if entity_info.get("exists"):
            # Entity already exists
            existing_entity = entity_info["entity_data"]
            message = f"""🔍 **Document Processed - Entity Confirmation Required**

**File:** {file_name}
**Document Type:** {doc_type}
**Detected Entity:** {entity_name} (confidence: {confidence:.0%})

**EXISTING ENTITY FOUND:**
**Name:** {existing_entity['name']}
**ID:** {existing_entity['id']}
**Folder:** {existing_entity['google_drive_folder_id'] or 'Not set'}

**Action:** Move file to existing entity folder?

**Please respond with your decision:**
• **To approve:** "yes", "approve", "looks good"
• **To correct entity:** "change to [correct name]", "it should be [entity name]"
• **To reject:** "no", "reject", "that's wrong"

File will remain in master folder until approved."""
        else:
            # New entity
            message = f"""🔍 **Document Processed - New Entity Creation Required**

**File:** {file_name}
**Document Type:** {doc_type}
**Detected Entity:** {entity_name} (confidence: {confidence:.0%})

**NEW ENTITY REQUIRED:**
Entity '{entity_name}' not found in database.

**Action:** Create new entity and folder?

**Please respond with your decision:**
• **To approve:** "yes", "approve", "create it"
• **To correct entity:** "change to [correct name]", "call it [entity name]"
• **To reject:** "no", "reject", "that's wrong"

File will remain in master folder until approved."""
        
        return message

    # NEW: Method to handle HDL approval responses
    async def handle_hdl_approval(self, request_id: str, decision: str, corrections: dict = None) -> dict:
        """Handle HDL approval response and execute file movement"""
        try:
            # Get the pending workflow
            workflow_state = await self._get_pending_workflow_by_request_id(request_id)
            
            if not workflow_state:
                return {"success": False, "error": "Workflow not found"}
            
            if decision in ["approve", "correct"]:
                # Apply corrections if provided
                if corrections and corrections.get('primary_value'):
                    workflow_state['entity_name'] = corrections['primary_value']
                
                # NOW execute the file movement workflow
                result = await self._execute_approved_workflow(workflow_state)
                return result
            else:
                # Rejected - mark as rejected and don't move file
                await self._mark_workflow_rejected(workflow_state)
                return {"success": True, "status": "rejected", "message": "Workflow rejected by human"}
                
        except Exception as e:
            logger.error(f"Error handling HDL approval: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _execute_approved_workflow(self, workflow_state: dict) -> dict:
        """Execute the approved workflow: Create folder → Move file → Update DB"""
        try:
            file_id = workflow_state["file_id"]
            file_name = workflow_state["file_name"]
            entity_name = workflow_state["entity_name"]
            analysis = workflow_state["analysis"]
            
            logger.info(f"🎯 Executing approved workflow for {file_name}")
            
            # Step 1: Create or get entity
            entity_info = await self._create_or_get_entity(entity_name, analysis)
            
            # Step 2: Create or get entity folder
            entity_folder_id = await self._ensure_entity_folder(entity_info)
            
            # Step 3: Move file to entity folder
            move_result = await self._move_file_to_entity_folder(file_id, entity_folder_id, file_name)
            
            if not move_result:
                return {"success": False, "error": "Failed to move file"}
            
            # Step 4: Update database
            await self._update_database_after_approval(file_id, file_name, entity_info, entity_folder_id, analysis)
            
            logger.info(f"✅ Approved workflow completed for {file_name}")
            logger.info(f"   Entity: {entity_name}")
            logger.info(f"   Moved to folder: {entity_folder_id}")
            
            return {"success": True, "entity_name": entity_name, "folder_id": entity_folder_id}
            
        except Exception as e:
            logger.error(f"Error executing approved workflow: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _create_or_get_entity(self, entity_name: str, analysis: dict) -> dict:
        """Create new entity or get existing one"""
        try:
            from ..core.database.service import DatabaseService
            
            db_service = DatabaseService()
            
            # Check if entity exists
            query = "SELECT id, name, google_drive_folder_id FROM entities WHERE name = %s"
            result = await db_service.execute_query(query, (entity_name,))
            
            if result:
                return {
                    "id": result[0]["id"],
                    "name": result[0]["name"],
                    "folder_id": result[0]["google_drive_folder_id"]
                }
            else:
                # Create new entity
                entity_type = self._determine_entity_type(entity_name, analysis)
                description = analysis.get("summary", f"Entity created from document analysis")
                
                insert_query = """
                    INSERT INTO entities (name, entity_type, description, created_at) 
                    VALUES (%s, %s, %s, NOW()) 
                    RETURNING id
                """
                
                insert_result = await db_service.execute_query(
                    insert_query, (entity_name, entity_type, description)
                )
                
                if insert_result:
                    entity_id = insert_result[0]["id"]
                    logger.info(f"Created new entity: {entity_name} with ID: {entity_id}")
                    
                    return {
                        "id": entity_id,
                        "name": entity_name,
                        "folder_id": None
                    }
                else:
                    raise Exception(f"Failed to create entity: {entity_name}")
                    
        except Exception as e:
            logger.error(f"Error creating/getting entity: {str(e)}")
            raise

    async def _update_database_after_approval(self, file_id: str, file_name: str, entity_info: dict, 
                                            entity_folder_id: str, analysis: dict):
        """Update database after approval with final paths"""
        try:
            from ..core.database.service import DatabaseService
            
            db_service = DatabaseService()
            
            # Update processed_files table
            update_processed_query = """
                UPDATE processed_files 
                SET entity_id = %s, processing_status = %s, current_folder_id = %s, approved_at = NOW()
                WHERE file_id = %s
            """
            
            await db_service.execute_query(update_processed_query, (
                entity_info["id"], "approved", entity_folder_id, file_id
            ))
            
            # Insert into document_metadata table
            doc_metadata_query = """
                INSERT INTO document_metadata 
                (entity_id, file_id, file_name, file_path, document_type, extraction_method, confidence_score, created_at) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """
            
            file_path = f"Entity - {entity_info['name']}/{file_name}"
            doc_type = analysis.get("document_type", "Document")
            extraction_method = analysis.get("extraction_method", "unknown")
            confidence = analysis.get("entity_confidence", 0.0)
            
            await db_service.execute_query(doc_metadata_query, (
                entity_info["id"], file_id, file_name, file_path, 
                doc_type, extraction_method, confidence
            ))
            
            logger.info(f"Database updated after approval for {file_name}")
            
        except Exception as e:
            logger.error(f"Error updating database after approval: {str(e)}")
            raise

    async def _get_pending_workflow_by_request_id(self, request_id: str) -> dict:
        """Get pending workflow state by HDL request ID"""
        try:
            # For now, we'll need to implement a way to link request_id to workflow
            # This is a simplified implementation - in production you'd store the request_id in the database
            
            # TODO: Implement proper request_id -> workflow mapping
            # For now, we'll return None to indicate we need to implement this properly
            logger.warning(f"Getting workflow by request_id {request_id} - implementation needed")
            return None
            
        except Exception as e:
            logger.error(f"Error getting pending workflow: {str(e)}")
            return None

    async def _mark_workflow_rejected(self, workflow_state: dict):
        """Mark workflow as rejected in database"""
        try:
            from ..core.database.service import DatabaseService
            
            db_service = DatabaseService()
            
            # Update processed_files table to rejected status
            update_query = """
                UPDATE processed_files 
                SET processing_status = %s, approved_at = NOW()
                WHERE file_id = %s
            """
            
            await db_service.execute_query(update_query, (
                "rejected", workflow_state["file_id"]
            ))
            
            logger.info(f"Marked workflow as rejected for {workflow_state['file_name']}")
            
        except Exception as e:
            logger.error(f"Error marking workflow rejected: {str(e)}")

    # Add connection to agent coordinator for HDL integration
    def set_agent_coordinator(self, agent_coordinator):
        """Set the agent coordinator for HDL communication"""
        self.agent_coordinator = agent_coordinator
        logger.info("Agent coordinator connected to scheduler service")

    async def _ensure_entity_folder(self, entity_info: dict) -> str:
        """Ensure entity has a Google Drive folder, create if needed"""
        try:
            entity_name = entity_info["name"]
            existing_folder_id = entity_info.get("folder_id")
            
            # If entity already has a folder, use it
            if existing_folder_id:
                logger.info(f"Using existing folder {existing_folder_id} for entity {entity_name}")
                return existing_folder_id
            
            # Create new folder for entity
            folder_name = f"Entity - {entity_name}"
            
            # Create folder in Google Drive
            folder_id = await self.drive_service.create_folder(folder_name)
            
            if folder_id:
                logger.info(f"Created new folder {folder_id} for entity {entity_name}")
                
                # Update entity with folder ID
                await self._update_entity_folder_id(entity_info["id"], folder_id)
                
                return folder_id
            else:
                logger.error(f"Failed to create folder for entity {entity_name}")
                return None
                
        except Exception as e:
            logger.error(f"Error ensuring entity folder: {str(e)}")
            return None

    async def _move_file_to_entity_folder(self, file_id: str, entity_folder_id: str, file_name: str) -> bool:
        """Move file from master folder to entity folder"""
        try:
            # Move file to entity folder
            success = await self.drive_service.move_file_to_folder(file_id, entity_folder_id)
            
            if success:
                logger.info(f"Successfully moved {file_name} to entity folder {entity_folder_id}")
                return True
            else:
                logger.error(f"Failed to move {file_name} to entity folder")
                return False
                
        except Exception as e:
            logger.error(f"Error moving file: {str(e)}")
            return False

    async def _update_entity_folder_id(self, entity_id: int, folder_id: str):
        """Update entity with Google Drive folder ID"""
        try:
            from ..core.database.service import DatabaseService
            
            db_service = DatabaseService()
            
            query = "UPDATE entities SET google_drive_folder_id = %s WHERE id = %s"
            await db_service.execute_query(query, (folder_id, entity_id))
            
            logger.info(f"Updated entity {entity_id} with folder ID {folder_id}")
            
        except Exception as e:
            logger.error(f"Error updating entity folder ID: {str(e)}")

    async def extract_images(self, file_id: str) -> List[Dict[str, Any]]:
        doc = fitz.open(temp_file)
        images = []
        
        for page_num in range(doc.page_count):
            page = doc[page_num]
            image_list = page.get_images()
            
            for img_index, img in enumerate(image_list):
                xref = img[0]
                base_image = doc.extract_image(xref)
                images.append({
                    "page": page_num + 1,
                    "index": img_index,
                    "width": base_image["width"],
                    "height": base_image["height"],
                    "format": base_image["ext"],
                    "data": base_image["image"]
                })

    async def _cleanup_temp_files(self):
        for file in self.temp_dir.glob("*"):
            try:
                file.unlink()
                logger.debug(f"Deleted temporary file: {file}")
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {file}: {str(e)}")

    async def _download_file(self, file_id: str) -> Optional[str]:
        # Create a temporary file with timestamp
        temp_file = self.temp_dir / f"{file_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        # Download and write file
        file_content = await self.drive_service.download_file(file_id)
        with open(temp_file, 'wb') as f:
            f.write(file_content)

    async def extract_text(self, file_id: str) -> Dict[str, Any]:
        # First validate the PDF
        validation_result = await self._validate_pdf(file_id)
        if not validation_result["is_valid"]:
            return {
                "success": False,
                "error": validation_result["error"],
                "is_scanned": validation_result["is_scanned"]
            }
        
        # Try PyMuPDF first (most reliable)
        try:
            text = await self._extract_with_pymupdf(file_id)
            if text and len(text.strip()) > 0:
                return {
                    "success": True,
                    "text": text,
                    "is_scanned": False,
                    "extraction_method": "pymupdf"
                }
        except Exception as e:
            logger.warning(f"PyMuPDF extraction failed: {str(e)}")

    def _determine_entity_type(self, entity_name: str, analysis: dict) -> str:
        """Determine entity type based on name and analysis"""
        entity_name_lower = entity_name.lower()
        
        # Common company indicators
        company_indicators = ["corp", "inc", "llc", "ltd", "company", "capital", "partners", "group"]
        
        # Check if it's a company
        if any(indicator in entity_name_lower for indicator in company_indicators):
            return "company"
        
        # Check if it's a person (has first and last name)
        if len(entity_name.split()) >= 2 and entity_name.split()[0][0].isupper():
            return "person"
        
        # Default to organization
        return "organization"