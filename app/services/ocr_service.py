from google.cloud import vision
from google.cloud.vision_v1 import types
import logging
from typing import Optional, Dict, Any, List
import asyncio
from ..core.config import get_settings
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import os
import tempfile
from pathlib import Path
import shutil
import fitz  # PyMuPDF
from PIL import Image
import base64
import json
from datetime import datetime, timedelta
import pickle

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class OCRService:
    """Service for handling OCR operations using Google Cloud Vision API."""
    
    def __init__(self):
        """Initialize the OCR service with Google Cloud Vision client."""
        try:
            self.settings = get_settings()
            logger.debug(f"Loading credentials from: {self.settings.get_google_credentials_path()}")
            
            # Initialize credentials with token refresh
            self.credentials = service_account.Credentials.from_service_account_file(
                self.settings.get_google_credentials_path(),
                scopes=['https://www.googleapis.com/auth/cloud-vision']
            )
            
            # Set token expiry to 55 minutes (5 minutes before the 60-minute limit)
            self.credentials.expiry = datetime.utcnow() + timedelta(minutes=55)
            
            logger.debug("Credentials loaded successfully")
            
            # Initialize the Vision client
            self.client = vision.ImageAnnotatorClient(credentials=self.credentials)
            logger.debug("Vision client initialized successfully")
            
            # Store the last token refresh time
            self.last_refresh = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Error initializing OCRService: {str(e)}")
            raise

    def __del__(self):
        """Cleanup temporary directory on object destruction."""
        try:
            if hasattr(self, 'temp_dir') and self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temp directory: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp directory: {str(e)}")

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
            logger.debug(f"Starting OCR text extraction for file: {file_id}")
            
            # Get file content from Google Drive
            file_content = await self._get_file_content(file_id)
            
            # Check if file is a PDF
            if file_id.lower().endswith('.pdf'):
                return await self._process_pdf(file_content, file_id)
            else:
                return await self._process_image(file_content, file_id)
                
        except Exception as e:
            logger.error(f"Error in OCR text extraction: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to extract text: {str(e)}",
                "file_id": file_id
            }

    async def _process_pdf(self, file_content: bytes, file_id: str) -> Dict[str, Any]:
        """Process PDF file for OCR."""
        try:
            # Create a temporary file for the PDF
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name
            
            try:
                # Open PDF with PyMuPDF
                doc = fitz.open(temp_file_path)
                total_pages = len(doc)
                logger.debug(f"Processing PDF with {total_pages} pages")
                
                all_text = []
                for page_num in range(total_pages):
                    try:
                        # Convert page to image
                        page = doc[page_num]
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better quality
                        
                        # Convert to PIL Image
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        
                        # Convert to bytes
                        img_byte_arr = io.BytesIO()
                        img.save(img_byte_arr, format='PNG')
                        img_byte_arr = img_byte_arr.getvalue()
                        
                        # Perform OCR on the image
                        image = vision.Image(content=img_byte_arr)
                        response = self.client.text_detection(image=image)
                        
                        if response.error.message:
                            logger.error(f"Error in Vision API: {response.error.message}")
                            continue
                        
                        if response.text_annotations:
                            page_text = response.text_annotations[0].description
                            if page_text.strip():
                                all_text.append(page_text)
                                logger.debug(f"Successfully extracted text from page {page_num + 1}")
                            else:
                                logger.warning(f"No text found on page {page_num + 1}")
                        else:
                            logger.warning(f"No text annotations found on page {page_num + 1}")
                            
                    except Exception as e:
                        logger.error(f"Error processing page {page_num + 1}: {str(e)}")
                        continue
                
                if all_text:
                    return {
                        "success": True,
                        "text": "\n\n".join(all_text),
                        "file_id": file_id,
                        "is_scanned": True
                    }
                else:
                    return {
                        "success": False,
                        "error": "No text could be extracted from the PDF",
                        "file_id": file_id,
                        "is_scanned": True
                    }
                    
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                except Exception as e:
                    logger.warning(f"Failed to remove temporary file: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to process PDF: {str(e)}",
                "file_id": file_id,
                "is_scanned": True
            }

    async def _process_image(self, file_content: bytes, file_id: str) -> Dict[str, Any]:
        """Process image file for OCR."""
        try:
            # Create image object for Vision API
            image = vision.Image(content=file_content)
            
            # Perform OCR
            response = self.client.text_detection(image=image)
            
            if response.error.message:
                logger.error(f"Error in Vision API: {response.error.message}")
                return {
                    "success": False,
                    "error": f"Vision API error: {response.error.message}",
                    "file_id": file_id
                }
            
            if response.text_annotations:
                text = response.text_annotations[0].description
                if text.strip():
                    return {
                        "success": True,
                        "text": text.strip(),
                        "file_id": file_id
                    }
                else:
                    return {
                        "success": False,
                        "error": "No text found in image",
                        "file_id": file_id
                    }
            else:
                return {
                    "success": False,
                    "error": "No text annotations found",
                    "file_id": file_id
                }
                
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to process image: {str(e)}",
                "file_id": file_id
            }

    async def _ensure_valid_token(self):
        """Ensure the token is valid and refresh if necessary."""
        try:
            # Check if token needs refresh (within 5 minutes of expiry)
            if datetime.utcnow() + timedelta(minutes=5) >= self.credentials.expiry:
                logger.debug("Token needs refresh, refreshing now...")
                
                # Refresh the token
                self.credentials.refresh(None)
                
                # Update expiry to 55 minutes from now
                self.credentials.expiry = datetime.utcnow() + timedelta(minutes=55)
                self.last_refresh = datetime.utcnow()
                
                logger.debug("Token refreshed successfully")
                
        except Exception as e:
            logger.error(f"Error refreshing token: {str(e)}")
            raise

    async def _get_file_content(self, file_id: str) -> bytes:
        """Get file content from Google Drive."""
        try:
            # Ensure token is valid before making the request
            await self._ensure_valid_token()
            
            from .google_drive import GoogleDriveService
            drive_service = GoogleDriveService()
            return await drive_service.download_file(file_id)
            
        except Exception as e:
            logger.error(f"Error getting file content: {str(e)}")
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
                "file_id": file_id,
                "is_scanned": extraction_result.get("is_scanned", False)
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