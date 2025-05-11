from google.cloud import vision
from google.cloud.vision_v1 import types
import logging
from typing import Optional, Dict, Any
import asyncio
from ..core.config import get_settings
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class OCRService:
    """Service for handling OCR operations using Google Cloud Vision API."""
    
    def __init__(self):
        """Initialize the OCR service with Google Cloud Vision client."""
        try:
            self.client = vision.ImageAnnotatorClient()
            self.settings = get_settings()
            
            # Initialize Google Drive API client
            credentials = service_account.Credentials.from_service_account_file(
                self.settings.GOOGLE_APPLICATION_CREDENTIALS,
                scopes=['https://www.googleapis.com/auth/drive.readonly']
            )
            self.drive_service = build('drive', 'v3', credentials=credentials)
            
            logger.info("OCR Service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize OCR Service: {str(e)}")
            raise

    async def extract_text(self, file_id: str) -> Dict[str, Any]:
        """
        Extract text from a document using Google Cloud Vision API.
        
        Args:
            file_id (str): The Google Drive file ID to process
            
        Returns:
            Dict[str, Any]: Dictionary containing:
                - success (bool): Whether the operation was successful
                - text (str): Extracted text if successful
                - error (str): Error message if unsuccessful
                - file_id (str): The processed file ID
        """
        try:
            logger.debug(f"Starting text extraction for file: {file_id}")
            
            # Get file content from Google Drive
            # Note: This is a placeholder - we'll need to implement the actual file download
            file_content = await self._get_file_content(file_id)
            
            # Create image object
            image = types.Image(content=file_content)
            
            # Perform text detection
            response = await asyncio.to_thread(
                self.client.document_text_detection,
                image=image
            )
            
            if response.error.message:
                logger.error(f"Error in OCR processing: {response.error.message}")
                return {
                    "success": False,
                    "error": response.error.message,
                    "file_id": file_id
                }
            
            # Extract text from response
            text = response.full_text_annotation.text
            
            logger.debug(f"Successfully extracted text from file: {file_id}")
            return {
                "success": True,
                "text": text,
                "file_id": file_id
            }
            
        except Exception as e:
            logger.error(f"Error in text extraction: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "file_id": file_id
            }

    async def _get_file_content(self, file_id: str) -> bytes:
        """
        Get file content from Google Drive.
        
        Args:
            file_id (str): The Google Drive file ID
            
        Returns:
            bytes: The file content
            
        Raises:
            Exception: If file download fails
        """
        try:
            logger.debug(f"Downloading file content for file ID: {file_id}")
            
            # Get file metadata to check MIME type
            file_metadata = self.drive_service.files().get(
                fileId=file_id,
                fields='mimeType'
            ).execute()
            
            mime_type = file_metadata.get('mimeType', '')
            
            # Download file content
            request = self.drive_service.files().get_media(fileId=file_id)
            file = io.BytesIO()
            downloader = MediaIoBaseDownload(file, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
                logger.debug(f"Download progress: {int(status.progress() * 100)}%")
            
            content = file.getvalue()
            logger.debug(f"Successfully downloaded file content for file ID: {file_id}")
            return content
            
        except Exception as e:
            logger.error(f"Error downloading file content: {str(e)}")
            raise

    async def process_document(self, file_id: str) -> Dict[str, Any]:
        """
        Process a document and extract structured information.
        
        Args:
            file_id (str): The Google Drive file ID to process
            
        Returns:
            Dict[str, Any]: Dictionary containing:
                - success (bool): Whether the operation was successful
                - data (Dict): Extracted data if successful
                - error (str): Error message if unsuccessful
                - file_id (str): The processed file ID
        """
        try:
            # Extract text from document
            extraction_result = await self.extract_text(file_id)
            
            if not extraction_result["success"]:
                return {
                    "success": False,
                    "error": extraction_result["error"],
                    "file_id": file_id
                }
            
            # Analyze text to extract structured data
            text = extraction_result["text"]
            structured_data = await self._analyze_text(text)
            
            return {
                "success": True,
                "data": {
                    "raw_text": text,
                    "extracted_fields": structured_data
                },
                "file_id": file_id
            }
            
        except Exception as e:
            logger.error(f"Error in document processing: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "file_id": file_id
            }

    async def _analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Analyze text to extract structured data based on the PRD's dataset design.
        
        Args:
            text (str): The text to analyze
            
        Returns:
            Dict[str, Any]: Dictionary containing extracted fields matching the PRD schema:
                - Task fields: ID, Description, Type, Entity, Due Date, Frequency, Status, Priority, Notes
                - Entity fields: ID, Name, Category, Contact Info, Notes
                - Obligation fields: ID, Description, Related Entity, Frequency, Trigger Date, Reminder Lead Time, Last Completed
                - Reminder fields: ID, Task ID, Method, Lead Time, Channel, Status
                - Authorization fields: ID, Entity, Task Type, Level, Expiry, Notes
        """
        try:
            # Split text into lines
            lines = text.split('\n')
            
            # Initialize result dictionary based on PRD schema
            result = {
                "task": {
                    "description": "",
                    "type": "",
                    "entity": "",
                    "due_date": "",
                    "frequency": "",
                    "status": "Pending",  # Default status
                    "priority": "",
                    "notes": ""
                },
                "entity": {
                    "name": "",
                    "category": "",
                    "contact_info": "",
                    "notes": ""
                },
                "obligation": {
                    "description": "",
                    "related_entity": "",
                    "frequency": "",
                    "trigger_date": "",
                    "reminder_lead_time": "",
                    "last_completed": ""
                },
                "reminder": {
                    "method": "",
                    "lead_time": "",
                    "channel": "",
                    "status": "Active"  # Default status
                },
                "authorization": {
                    "entity": "",
                    "task_type": "",
                    "level": "",
                    "expiry": "",
                    "notes": ""
                }
            }
            
            # Extract information using patterns
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Try to extract dates (assuming format: MM/DD/YYYY or similar)
                if any(char.isdigit() for char in line) and ('/' in line or '-' in line):
                    # Check if it's a due date, trigger date, or expiry
                    if 'DUE' in line.upper() or 'DUE DATE' in line.upper():
                        result["task"]["due_date"] = line
                    elif 'TRIGGER' in line.upper() or 'START' in line.upper():
                        result["obligation"]["trigger_date"] = line
                    elif 'EXPIR' in line.upper() or 'VALID' in line.upper():
                        result["authorization"]["expiry"] = line
                    elif 'COMPLETED' in line.upper() or 'LAST' in line.upper():
                        result["obligation"]["last_completed"] = line
                
                # Try to extract frequency information
                if any(word in line.upper() for word in ['MONTHLY', 'WEEKLY', 'DAILY', 'YEARLY', 'QUARTERLY']):
                    if 'OBLIGATION' in line.upper() or 'RECURRING' in line.upper():
                        result["obligation"]["frequency"] = line
                    else:
                        result["task"]["frequency"] = line
                
                # Try to extract entity information
                if 'ENTITY' in line.upper() or 'COMPANY' in line.upper() or 'ORGANIZATION' in line.upper():
                    result["entity"]["name"] = line
                elif 'CATEGORY' in line.upper() or 'TYPE' in line.upper():
                    result["entity"]["category"] = line
                elif '@' in line or '.COM' in line.upper() or '.ORG' in line.upper():
                    result["entity"]["contact_info"] = line
                
                # Try to extract task information
                if 'TASK' in line.upper() or 'DESCRIPTION' in line.upper():
                    result["task"]["description"] = line
                elif 'PRIORITY' in line.upper():
                    result["task"]["priority"] = line
                elif 'NOTES' in line.upper() or 'COMMENTS' in line.upper():
                    result["task"]["notes"] = line
                
                # Try to extract reminder information
                if 'REMINDER' in line.upper() or 'NOTIFICATION' in line.upper():
                    if 'LEAD' in line.upper() or 'BEFORE' in line.upper():
                        result["reminder"]["lead_time"] = line
                    elif 'CHANNEL' in line.upper() or 'METHOD' in line.upper():
                        result["reminder"]["method"] = line
                
                # Try to extract authorization information
                if 'AUTHORIZATION' in line.upper() or 'AUTH' in line.upper():
                    if 'LEVEL' in line.upper():
                        result["authorization"]["level"] = line
                    elif 'TYPE' in line.upper():
                        result["authorization"]["task_type"] = line
                    elif 'NOTES' in line.upper():
                        result["authorization"]["notes"] = line
            
            # Clean up results
            for section in result:
                for key in result[section]:
                    if isinstance(result[section][key], str):
                        result[section][key] = result[section][key].strip()
            
            return result
            
        except Exception as e:
            logger.error(f"Error in text analysis: {str(e)}")
            return {} 