from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
from .google_drive import GoogleDriveService
from .document_processor import DocumentProcessorService

logger = logging.getLogger(__name__)

class FileDiscoveryService:
    """Service for managing file discovery and processing queue."""
    
    def __init__(self):
        """Initialize the file discovery service."""
        self.drive_service: Optional[GoogleDriveService] = None
        self.document_processor: Optional[DocumentProcessorService] = None
        self.processing_queue: List[Dict[str, Any]] = []
        self.supported_mime_types = {
            'application/pdf': 'PDF',
            'image/jpeg': 'Image',
            'image/png': 'Image',
            'application/vnd.google-apps.document': 'Google Doc',
            'application/vnd.google-apps.spreadsheet': 'Google Sheet'
        }
        logger.info("File Discovery Service initialized")

    async def initialize(self, drive_service: GoogleDriveService, document_processor: DocumentProcessorService):
        """Initialize the service with required dependencies."""
        self.drive_service = drive_service
        self.document_processor = document_processor
        logger.info("File Discovery Service initialized with dependencies")

    async def scan_folder(self) -> Dict[str, Any]:
        """
        Scan the Google Drive folder for new files.
        
        Returns:
            Dict[str, Any]: Result of the scan operation
        """
        try:
            logger.info("Starting folder scan")
            
            if not self.drive_service:
                raise ValueError("Drive service not initialized")
            
            # Get files from the master folder
            files = await self.drive_service.get_folder_contents()
            logger.info(f"Found {len(files) if files else 0} files in folder")
            
            if not files:
                logger.info("No files found in folder")
                return {
                    "success": True,
                    "message": "No files found in folder",
                    "files_processed": 0
                }
            
            # Log all found files
            for file in files:
                logger.info(f"Found file: {file['name']} (ID: {file['id']}, Type: {file.get('mimeType', 'unknown')})")
            
            # Process each file
            processed_count = 0
            for file in files:
                try:
                    logger.info(f"Processing file: {file['name']}")
                    
                    # Validate file
                    validation_result = await self._validate_file(file)
                    logger.info(f"Validation result for {file['name']}: {validation_result}")
                    
                    if not validation_result["is_valid"]:
                        logger.warning(f"File {file['name']} failed validation: {validation_result['reason']}")
                        continue
                    
                    # Check if already processed
                    is_processed = await self._is_file_processed(file['id'])
                    logger.info(f"File {file['name']} processed status: {is_processed}")
                    
                    if is_processed:
                        logger.info(f"File {file['name']} already processed, skipping")
                        continue
                    
                    # Add to processing queue
                    self.processing_queue.append({
                        "file": file,
                        "discovery_time": datetime.now().isoformat(),
                        "status": "pending"
                    })
                    processed_count += 1
                    logger.info(f"Added file {file['name']} to processing queue")
                    
                except Exception as e:
                    logger.error(f"Error processing file {file['name']}: {str(e)}")
                    continue
            
            # Process queue if we have files
            if processed_count > 0:
                logger.info(f"Starting queue processing for {processed_count} files")
                await self._process_queue()
            else:
                logger.info("No new files to process")
            
            return {
                "success": True,
                "message": f"Processed {processed_count} new files",
                "files_processed": processed_count
            }
            
        except Exception as e:
            logger.error(f"Error in folder scan: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "files_processed": 0
            }

    async def _validate_file(self, file: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a file for processing.
        
        Args:
            file (Dict[str, Any]): File information from Google Drive
            
        Returns:
            Dict[str, Any]: Validation result
        """
        try:
            # Get file metadata
            metadata = await self.drive_service.get_file_metadata(file['id'])
            mime_type = metadata.get('mimeType', '')
            
            # Check if file type is supported
            if mime_type not in self.supported_mime_types:
                return {
                    "is_valid": False,
                    "reason": f"Unsupported file type: {mime_type}"
                }
            
            return {
                "is_valid": True,
                "file_type": self.supported_mime_types[mime_type]
            }
            
        except Exception as e:
            logger.error(f"Error validating file: {str(e)}")
            return {
                "is_valid": False,
                "reason": f"Validation error: {str(e)}"
            }

    async def _is_file_processed(self, file_id: str) -> bool:
        """
        Check if a file has been previously processed.
        
        Args:
            file_id (str): Google Drive file ID
            
        Returns:
            bool: True if file has been processed, False otherwise
        """
        # TODO: Implement database check for processing history
        # For now, return False to process all files
        return False

    async def _process_queue(self):
        """Process files in the queue in FIFO order."""
        try:
            logger.info(f"Processing queue with {len(self.processing_queue)} files")
            
            if not self.document_processor:
                raise ValueError("Document processor not initialized")
            
            # Create a copy of the queue to process
            queue_to_process = self.processing_queue.copy()
            self.processing_queue.clear()
            
            for queue_item in queue_to_process:
                file = queue_item["file"]
                
                try:
                    logger.info(f"Processing file: {file['name']}")
                    
                    # Update status
                    queue_item["status"] = "processing"
                    
                    # Process document
                    result = await self.document_processor.process_document(file['id'])
                    
                    if result["success"]:
                        queue_item["status"] = "completed"
                        logger.info(f"Successfully processed file: {file['name']}")
                    else:
                        queue_item["status"] = "failed"
                        queue_item["error"] = result.get("error", "Unknown error")
                        logger.error(f"Failed to process file {file['name']}: {result.get('error')}")
                    
                except Exception as e:
                    queue_item["status"] = "failed"
                    queue_item["error"] = str(e)
                    logger.error(f"Error processing file {file['name']}: {str(e)}")
            
            logger.info("Queue processing completed")
            
        except Exception as e:
            logger.error(f"Error processing queue: {str(e)}")
            raise 