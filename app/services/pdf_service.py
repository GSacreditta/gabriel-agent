import PyPDF2
import io
import logging
from typing import Dict, Any, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from ..core.config import get_settings

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class PDFService:
    """Service for handling PDF operations."""
    
    def __init__(self):
        """Initialize the PDF service with Google Drive client."""
        try:
            self.settings = get_settings()
            
            # Initialize Google Drive API client
            credentials = service_account.Credentials.from_service_account_file(
                self.settings.GOOGLE_APPLICATION_CREDENTIALS,
                scopes=['https://www.googleapis.com/auth/drive.readonly']
            )
            self.drive_service = build('drive', 'v3', credentials=credentials)
            
            logger.info("PDF Service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize PDF Service: {str(e)}")
            raise

    async def extract_text(self, file_id: str) -> Dict[str, Any]:
        """
        Extract text from a PDF file.
        
        Args:
            file_id (str): The Google Drive file ID to process
            
        Returns:
            Dict[str, Any]: Dictionary containing:
                - success (bool): Whether the operation was successful
                - text (str): Extracted text if successful
                - error (str): Error message if unsuccessful
                - file_id (str): The processed file ID
                - is_scanned (bool): Whether the PDF appears to be scanned
        """
        try:
            logger.debug(f"Starting PDF text extraction for file: {file_id}")
            
            # Get file content from Google Drive
            file_content = await self._get_file_content(file_id)
            
            # Create PDF reader object
            pdf_file = io.BytesIO(file_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            # Extract text from all pages
            text = ""
            is_scanned = False
            total_pages = len(pdf_reader.pages)
            pages_with_text = 0
            
            for page in pdf_reader.pages:
                try:
                    page_text = page.extract_text()
                    if page_text and page_text.strip():
                        text += page_text + "\n"
                        pages_with_text += 1
                except Exception as e:
                    logger.warning(f"Error extracting text from page: {str(e)}")
                    is_scanned = True
            
            # If no text was extracted or less than 50% of pages have text, consider it scanned
            if not text.strip() or (pages_with_text / total_pages) < 0.5:
                is_scanned = True
                logger.info(f"PDF appears to be scanned: {file_id}")
                return {
                    "success": False,
                    "error": "PDF appears to be scanned or contains no extractable text",
                    "is_scanned": True,
                    "file_id": file_id
                }
            
            logger.debug(f"Successfully extracted text from PDF: {file_id}")
            return {
                "success": True,
                "text": text,
                "is_scanned": False,
                "file_id": file_id
            }
            
        except Exception as e:
            logger.error(f"Error in PDF text extraction: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "file_id": file_id,
                "is_scanned": True  # Assume scanned on error
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
            
            if mime_type != 'application/pdf':
                raise ValueError(f"File is not a PDF. MIME type: {mime_type}")
            
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