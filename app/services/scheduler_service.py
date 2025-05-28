# gabriel-agent/app/services/scheduler_service.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging
from datetime import datetime
from typing import Optional
from .google_drive import GoogleDriveService
from .agent import create_agent
from .ocr_service import OCRService
from .vector_storage_service import VectorStorageService

logger = logging.getLogger(__name__)

class SchedulerService:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.drive_service: Optional[GoogleDriveService] = None
        self.agent = None
        self.slack_service = None
        self.is_running = False

    async def initialize(self, drive_service: GoogleDriveService, agent, slack_service=None):
        """Initialize the scheduler with required services."""
        self.drive_service = drive_service
        self.agent = agent
        self.slack_service = slack_service
        self.scheduler.add_job(
            self.scan_documents,
            trigger=IntervalTrigger(minutes=30),
            id='scan_documents',
            replace_existing=True
        )
        logger.info("Scheduler initialized with document scanning job")

    def start(self):
        """Start the scheduler."""
        if not self.is_running:
            self.scheduler.start()
            self.is_running = True
            logger.info("Scheduler started")

    def stop(self):
        """Stop the scheduler."""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Scheduler stopped")

    async def scan_documents(self):
        """Scan for new documents in the Google Drive folder."""
        try:
            logger.info("Starting scheduled document scan")
            
            if not self.drive_service or not self.agent:
                logger.error("Required services not initialized")
                return

            # Get current time for logging
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 1. Get files from the master folder
            files = self.drive_service.get_folder_contents()
            
            if not files:
                logger.info("No files found in master folder")
                return

            # Process each file
            for file in files:
                try:
                    logger.info(f"Processing file: {file['name']}")
                    
                    # 2. Identify file format and metadata
                    file_metadata = await self.drive_service.get_file_metadata(file['id'])
                    logger.info(f"File metadata: {file_metadata}")
                    
                    # 3. Process document with OCR and extract information
                    ocr_service = OCRService()
                    ocr_result = await ocr_service.process_document(file['id'])
                    
                    if not ocr_result["success"]:
                        logger.error(f"OCR processing failed for {file['name']}: {ocr_result.get('error')}")
                        continue
                    
                    # 4. Extract entity name and key information
                    entity_name = ocr_result["data"]["extracted_fields"]["entity_name"]
                    
                    # 5. Prepare results for human review
                    document_info = {
                        "entity_name": entity_name,
                        "file_name": file['name'],
                        "file_id": file['id'],
                        "processing_time": current_time,
                        "ocr_result": ocr_result
                    }
                    
                    # 6. Plan tasks for human review
                    review_tasks = await self.agent.plan_review_tasks(document_info)
                    
                    # 7. Identify similar entity Sub-Folder
                    folder_result = await self.drive_service.create_or_match_folder(entity_name)
                    
                    # 8. Move file to similar entity Sub-Folder
                    move_result = await self.drive_service.move_file_to_folder(
                        file_id=file['id'],
                        folder_id=folder_result["folder_id"]
                    )
                    
                    # 9. Store in Vector Database
                    vector_service = VectorStorageService()
                    await vector_service.store_document(
                        document_id=file['id'],
                        content=ocr_result["text"],
                        metadata=document_info
                    )
                    
                    # 10. Send notification to Slack
                    if self.slack_service:
                        await self.slack_service.send_message(
                            message=f"Processed document: {file['name']}\nEntity: {entity_name}\nTasks: {review_tasks}",
                            channel=self.slack_service.default_channel
                        )
                    
                    logger.info(f"Successfully processed file: {file['name']}")
                    
                except Exception as e:
                    logger.error(f"Error processing file {file['name']}: {str(e)}")
                    continue

            logger.info("Completed scheduled document scan")
            
        except Exception as e:
            logger.error(f"Error in scheduled document scan: {str(e)}")