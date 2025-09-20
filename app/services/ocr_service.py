import logging
from typing import Optional, Dict, Any, List
import asyncio
from ..core.config import get_settings
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
import PyPDF2
import re

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Try to import Google Cloud Vision - make it optional
try:
    from google.cloud import vision
    from google.cloud.vision_v1 import types
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    GOOGLE_VISION_AVAILABLE = True
    logger.info("Google Cloud Vision imported successfully")
except ImportError as e:
    GOOGLE_VISION_AVAILABLE = False
    logger.warning(f"Google Cloud Vision not available: {e}. OCR will fall back to PDF text extraction only.")

class OCRService:
    """Service for OCR and text extraction from documents."""
    
    def __init__(self):
        """Initialize the OCR service with Google Cloud Vision client."""
        self.temp_dir = Path(tempfile.mkdtemp(prefix="gabriel_agent_ocr_"))
        self.drive_service = None  # Will be injected by main.py
        
        if GOOGLE_VISION_AVAILABLE:
            try:
                self.client = vision.ImageAnnotatorClient()
                self.vision_enabled = True
                logger.info("OCR Service initialized with Google Cloud Vision")
            except Exception as e:
                logger.warning(f"Failed to initialize Google Cloud Vision client: {str(e)}")
                self.client = None
                self.vision_enabled = False
        else:
            self.client = None
            self.vision_enabled = False
            logger.info("OCR Service initialized without Google Cloud Vision (using PDF text extraction only)")

    def set_drive_service(self, drive_service):
        """Inject Google Drive service for file access."""
        self.drive_service = drive_service
    
    async def process_document(self, file_path: str, file_name: str = None, mime_type: str = None) -> Dict[str, Any]:
        """Process a document with OCR and extract structured information.
        
        Args:
            file_path: Path to the document file
            file_name: Optional name of the file
            mime_type: Optional MIME type of the file
            
        Returns:
            Dict containing OCR results and extracted information
        """
        try:
            logger.info(f"Processing document: {file_name or file_path}")
            
            # For PDFs, try PDF service first
            if mime_type == "application/pdf":
                try:
                    from .pdf_service import PDFService
                    pdf_service = PDFService()
                    pdf_result = await pdf_service.extract_text(file_path)
                    
                    if pdf_result["success"] and pdf_result.get("text"):
                        logger.info("Successfully extracted text using PDF service")
                        return {
                            "success": True,
                            "data": {
                                "raw_text": pdf_result["text"],
                                "extracted_fields": await self._extract_fields(pdf_result["text"]),
                                "char_count": len(pdf_result["text"]),
                                "method": "pdf_service"
                            }
                        }
                    else:
                        logger.warning(f"PDF service extraction failed: {pdf_result.get('error')}")
                        if pdf_result.get("is_scanned"):
                            logger.info("Document appears to be scanned, proceeding with OCR")
                except Exception as e:
                    logger.warning(f"Error using PDF service: {str(e)}")
            
            # Process with OCR if available
            if self.vision_enabled:
                logger.info("Processing with Google Cloud Vision OCR")
                ocr_result = await self._process_with_vision(file_path)
                
                if not ocr_result["success"]:
                    return ocr_result
            else:
                logger.warning("Google Cloud Vision not available, cannot perform OCR on non-PDF files")
                return {
                    "success": False,
                    "error": "Google Cloud Vision not available and document is not a PDF or PDF text extraction failed"
                }
            
            extracted_text = ocr_result["text"]
            extracted_fields = await self._extract_fields(extracted_text)
            
            return {
                "success": True,
                "data": {
                    "raw_text": extracted_text,
                    "extracted_fields": extracted_fields,
                    "char_count": len(extracted_text),
                    "method": "google_vision_ocr"
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _process_with_vision(self, file_path: str) -> Dict[str, Any]:
        """Process a document with Google Cloud Vision OCR.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Dict containing OCR results
        """
        if not self.vision_enabled or not self.client:
            return {
                "success": False,
                "error": "Google Cloud Vision is not available"
            }
            
        try:
            # Read the file content
            with open(file_path, 'rb') as image_file:
                content = image_file.read()
            
            image = vision.Image(content=content)
            
            # Perform OCR
            response = self.client.document_text_detection(image=image)
            
            if response.error.message:
                raise Exception(
                    f"Error detected in OCR response: {response.error.message}"
                )
            
            # Extract full text
            text = response.full_text_annotation.text
            
            if not text:
                return {
                    "success": False,
                    "error": "No text detected in document"
                }
            
            return {
                "success": True,
                "text": text
            }
            
        except Exception as e:
            logger.error(f"Error in OCR processing: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _extract_fields(self, text: str) -> Dict[str, Any]:
        """Extract structured fields from text.
        
        Args:
            text: Text to extract fields from
            
        Returns:
            Dict containing extracted fields
        """
        try:
            # Extract dates
            date_pattern = r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b'
            dates = re.findall(date_pattern, text, re.IGNORECASE)
            
            # Extract monetary amounts
            amount_pattern = r'\$\s*\d+(?:,\d{3})*(?:\.\d{2})?|\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:USD|EUR|GBP)'
            amounts = re.findall(amount_pattern, text)
            
            # Extract email addresses
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            emails = re.findall(email_pattern, text)
            
            # Extract names (basic)
            name_pattern = r'Mr\.|Mrs\.|Ms\.|Dr\.|Prof\. [A-Z][a-z]+ [A-Z][a-z]+'
            names = re.findall(name_pattern, text)
            
            return {
                "dates": dates,
                "monetary_amounts": amounts,
                "emails": emails,
                "names": names
            }
            
        except Exception as e:
            logger.error(f"Error extracting fields: {str(e)}")
            return {}

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
            
            # Get file metadata to determine the MIME type
            if not self.drive_service:
                logger.error("Google Drive service not injected - cannot access files")
                return {
                    "success": False,
                    "error": "Google Drive service not available",
                    "file_id": file_id
                }
            
            file_metadata = await self.drive_service.get_file_metadata(file_id)
            mime_type = file_metadata.get('mimeType', '')
            file_name = file_metadata.get('name', 'unknown')
            
            logger.info(f"Processing file: {file_name} (MIME type: {mime_type})")
            
            # Get file content from Google Drive
            file_content = await self._get_file_content(file_id)
            
            # Check if file is a PDF based on MIME type
            if mime_type == 'application/pdf':
                logger.info(f"Detected PDF file: {file_name}, using PDF processing")
                return await self._process_pdf(file_content)
            else:
                logger.info(f"Detected image/other file: {file_name}, using image processing")
                return await self._process_image(file_content, file_id)
                
        except Exception as e:
            logger.error(f"Error in OCR text extraction: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to extract text: {str(e)}",
                "file_id": file_id
            }

    async def _process_pdf(self, file_content: bytes, file_id: str) -> Dict[str, Any]:
        """Process PDF file - try direct text extraction first, then OCR if needed."""
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
                
                # FIRST: Try direct text extraction (for text-based PDFs)
                all_text = []
                text_found = False
                
                for page_num in range(total_pages):
                    try:
                        page = doc[page_num]
                        # Extract text directly from PDF
                        page_text = page.get_text()
                        
                        if page_text.strip():
                            all_text.append(page_text.strip())
                            text_found = True
                            logger.debug(f"Successfully extracted text directly from page {page_num + 1}")
                        else:
                            logger.debug(f"No direct text found on page {page_num + 1}")
                            
                    except Exception as e:
                        logger.error(f"Error extracting text from page {page_num + 1}: {str(e)}")
                        continue
                
                # If we found text via direct extraction, return it
                if text_found and all_text:
                    combined_text = "\n\n".join(all_text)
                    logger.info(f"Successfully extracted {len(combined_text)} characters of text directly from PDF")
                    return {
                        "success": True,
                        "text": combined_text,
                        "file_id": file_id,
                        "is_scanned": False,  # This is a text-based PDF
                        "extraction_method": "direct_text"
                    }
                
                # SECOND: If no text found, try OCR (for scanned/image-based PDFs)
                logger.info("No direct text found in PDF, attempting OCR on page images...")
                
                ocr_text = []
                for page_num in range(min(total_pages, 5)):  # Limit to first 5 pages for OCR
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
                        
                        # Perform OCR on the image if Vision is available
                        if not self.vision_enabled or not self.client:
                            logger.warning("Google Cloud Vision not available for OCR processing")
                            continue
                            
                        image = vision.Image(content=img_byte_arr)
                        response = self.client.text_detection(image=image)
                        
                        if response.error.message:
                            logger.warning(f"Vision API error on page {page_num + 1}: {response.error.message}")
                            continue
                        
                        if response.text_annotations:
                            page_text = response.text_annotations[0].description
                            if page_text.strip():
                                ocr_text.append(page_text)
                                logger.debug(f"Successfully extracted text via OCR from page {page_num + 1}")
                            else:
                                logger.warning(f"No text found via OCR on page {page_num + 1}")
                        else:
                            logger.warning(f"No text annotations found via OCR on page {page_num + 1}")
                            
                    except Exception as e:
                        logger.error(f"Error performing OCR on page {page_num + 1}: {str(e)}")
                        continue
                
                if ocr_text:
                    combined_ocr_text = "\n\n".join(ocr_text)
                    logger.info(f"Successfully extracted {len(combined_ocr_text)} characters via OCR")
                    return {
                        "success": True,
                        "text": combined_ocr_text,
                        "file_id": file_id,
                        "is_scanned": True,  # This is a scanned/image-based PDF
                        "extraction_method": "ocr"
                    }
                else:
                    return {
                        "success": False,
                        "error": "No text could be extracted from the PDF using either direct extraction or OCR",
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
        if not self.vision_enabled or not self.client:
            return {
                "success": False,
                "error": "Google Cloud Vision is not available for image processing",
                "file_id": file_id
            }
            
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
            
            if not self.drive_service:
                logger.error("Google Drive service not injected - cannot download file")
                return {
                    "success": False,
                    "error": "Google Drive service not available"
                }
            drive_service = self.drive_service
            return await drive_service.download_file(file_id)
            
        except Exception as e:
            logger.error(f"Error getting file content: {str(e)}")
            raise

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