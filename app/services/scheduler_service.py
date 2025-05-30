# gabriel-agent/app/services/scheduler_service.py

import asyncio
import logging
from datetime import datetime, timedelta
from ..core.config import get_settings
from .google_drive import GoogleDriveService
from .agent import Agent
from .slack_service import SlackService
from .file_discovery_service import FileDiscoveryService
from .document_processor import DocumentProcessor
import fitz
from typing import List, Dict, Any, Optional
from googleapiclient.discovery import build

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class SchedulerService:
    """Service for scheduling and triggering document scans."""
    
    def __init__(self):
        """Initialize the scheduler service."""
        self.settings = get_settings()
        self.drive_service = GoogleDriveService()
        self.agent: Optional[Agent] = None
        self.slack_service: Optional[SlackService] = None
        self.file_discovery: Optional[FileDiscoveryService] = None
        self.document_processor = DocumentProcessor()
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
        file_discovery: FileDiscoveryService
    ):
        """Initialize the service with required dependencies."""
        self.agent = agent
        self.slack_service = slack_service
        self.file_discovery = file_discovery
        logger.info("Scheduler Service initialized with dependencies")

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
                await self.scan_documents()
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

    async def scan_documents(self):
        """Scan for new documents and process them."""
        try:
            logger.info("Starting document scan")
            
            # Get folder contents
            files = await self.drive_service.get_folder_contents()
            logger.debug(f"Found {len(files)} files in folder")
            
            if not files:
                logger.info("No files found to process")
                return
            
            # Process each file
            for file in files:
                try:
                    logger.debug(f"Processing file: {file.get('name')}")
                    
                    # Skip if not a document
                    if not self._is_document(file.get('mimeType')):
                        logger.debug(f"Skipping non-document file: {file.get('name')}")
                        continue
                    
                    # Process the document
                    result = await self.document_processor.process_document(file)
                    
                    if result.get('success'):
                        # Send success notification
                        await self.slack_service.send_message(
                            f"✅ Successfully processed document: {file.get('name')}\n"
                            f"Summary: {result.get('summary', 'No summary available')}"
                        )
                    else:
                        # Send error notification
                        await self.slack_service.send_message(
                            f"❌ Error processing document: {file.get('name')}\n"
                            f"Error: {result.get('error', 'Unknown error')}"
                        )
                        
                except Exception as e:
                    logger.error(f"Error processing file {file.get('name')}: {str(e)}")
                    await self.slack_service.send_message(
                        f"❌ Error processing document: {file.get('name')}\n"
                        f"Error: {str(e)}"
                    )
            
            logger.info("Document scan completed")
            
        except Exception as e:
            error_msg = f"Error during document scan: {str(e)}"
            logger.error(error_msg)
            await self.slack_service.send_message(f"❌ {error_msg}")
            raise

    def _is_document(self, mime_type: str) -> bool:
        """Check if the file is a document type."""
        document_types = [
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'text/plain',
            'text/csv'
        ]
        return mime_type in document_types

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