import PyPDF2
import io
import logging
from typing import Dict, Any, Optional, List
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from ..core.config import get_settings
import fitz  # PyMuPDF
import tempfile
import os
from pathlib import Path
from langchain_community.document_loaders.parsers.pdf import (
    PyMuPDFParser,
    PDFPlumberParser,
    PDFMinerParser
)
from langchain_core.documents import Document
from .google_drive import GoogleDriveService
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class PDFService:
    """Service for handling PDF operations."""
    
    def __init__(self):
        """Initialize the PDF service with necessary configurations."""
        self.settings = get_settings()
        self.temp_dir = Path(tempfile.mkdtemp(prefix="gabriel_agent_"))
        logger.info(f"PDF Service initialized with temp directory: {self.temp_dir}")
        
        # Initialize Google Drive service
        self.drive_service = GoogleDriveService()
        logger.info("Google Drive service initialized")
        
        # Initialize LangChain parsers
        self.pymupdf_parser = PyMuPDFParser(
            text_kwargs={"sort": True},  # Sort text in reading order
            extract_images=True
        )
        self.pdfplumber_parser = PDFPlumberParser(
            text_kwargs={"layout": True},  # Preserve layout
            dedupe=True,  # Remove duplicate characters
            extract_images=True
        )
        self.pdfminer_parser = PDFMinerParser(
            extract_images=True,
            concatenate_pages=True
        )

    async def extract_text(self, file_id: str) -> Dict[str, Any]:
        """
        Extract text from a PDF file using multiple methods.
        
        Args:
            file_id: Google Drive file ID
            
        Returns:
            Dict containing:
            - success: bool
            - text: str (if successful)
            - is_scanned: bool
            - extraction_method: str
            - error: str (if failed)
        """
        try:
            logger.debug(f"Starting text extraction for file: {file_id}")
            
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
                logger.debug("Attempting text extraction with PyMuPDF")
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
            
            # Try PyPDF2 as fallback
            try:
                logger.debug("Attempting text extraction with PyPDF2")
                text = await self._extract_with_pypdf2(file_id)
                if text and len(text.strip()) > 0:
                    return {
                        "success": True,
                        "text": text,
                        "is_scanned": False,
                        "extraction_method": "pypdf2"
                    }
            except Exception as e:
                logger.warning(f"PyPDF2 extraction failed: {str(e)}")
            
            # If both methods fail, it's likely a scanned document
            return {
                "success": False,
                "error": "No text could be extracted. Document may be scanned or image-based.",
                "is_scanned": True
            }
            
        except Exception as e:
            logger.error(f"Error in extract_text: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "is_scanned": False
            }
        finally:
            # Cleanup temporary files
            await self._cleanup_temp_files()

    async def _validate_pdf(self, file_id: str) -> Dict[str, Any]:
        """
        Validate a PDF file before processing.
        
        Args:
            file_id: Google Drive file ID
            
        Returns:
            Dict containing validation results
        """
        try:
            logger.debug(f"Validating PDF file: {file_id}")
            
            # Download the file
            temp_file = await self._download_file(file_id)
            if not temp_file:
                return {
                    "is_valid": False,
                    "error": "Failed to download file",
                    "is_scanned": False
                }
            
            # Open with PyMuPDF
            doc = fitz.open(temp_file)
            
            # Check if PDF is encrypted
            if doc.is_encrypted:
                return {
                    "is_valid": False,
                    "error": "PDF is encrypted",
                    "is_scanned": False
                }
            
            # Check if PDF has pages
            if doc.page_count == 0:
                return {
                    "is_valid": False,
                    "error": "PDF has no pages",
                    "is_scanned": False
                }
            
            # Check if first page has extractable text
            first_page = doc[0]
            text = first_page.get_text()
            is_scanned = len(text.strip()) == 0
            
            doc.close()
            
            return {
                "is_valid": True,
                "is_scanned": is_scanned
            }
            
        except Exception as e:
            logger.error(f"Error in _validate_pdf: {str(e)}")
            return {
                "is_valid": False,
                "error": str(e),
                "is_scanned": False
            }

    async def _extract_with_pymupdf(self, file_id: str) -> str:
        """Extract text using PyMuPDF."""
        try:
            temp_file = await self._download_file(file_id)
            if not temp_file:
                raise Exception("Failed to download file")
            
            doc = fitz.open(temp_file)
            text = ""
            
            for page_num in range(doc.page_count):
                page = doc[page_num]
                text += page.get_text()
            
            doc.close()
            return text
            
        except Exception as e:
            logger.error(f"Error in _extract_with_pymupdf: {str(e)}")
            raise

    async def _extract_with_pypdf2(self, file_id: str) -> str:
        """Extract text using PyPDF2."""
        try:
            temp_file = await self._download_file(file_id)
            if not temp_file:
                raise Exception("Failed to download file")
            
            with open(temp_file, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                
                for page in reader.pages:
                    text += page.extract_text()
                
                return text
                
        except Exception as e:
            logger.error(f"Error in _extract_with_pypdf2: {str(e)}")
            raise

    async def _download_file(self, file_id: str) -> Optional[str]:
        """Download a file from Google Drive to a temporary location."""
        try:
            logger.debug(f"Downloading file: {file_id}")
            
            # Create a temporary file
            temp_file = self.temp_dir / f"{file_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            
            # Download the file
            file_content = await self.drive_service.download_file(file_id)
            
            # Write to temporary file
            with open(temp_file, 'wb') as f:
                f.write(file_content)
            
            logger.debug(f"File downloaded to: {temp_file}")
            return str(temp_file)
            
        except Exception as e:
            logger.error(f"Error in _download_file: {str(e)}")
            return None

    async def _cleanup_temp_files(self):
        """Clean up temporary files."""
        try:
            for file in self.temp_dir.glob("*"):
                try:
                    file.unlink()
                    logger.debug(f"Deleted temporary file: {file}")
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file {file}: {str(e)}")
        except Exception as e:
            logger.error(f"Error in _cleanup_temp_files: {str(e)}")

    async def get_pdf_metadata(self, file_id: str) -> Dict[str, Any]:
        """
        Get metadata from a PDF file.
        
        Args:
            file_id: Google Drive file ID
            
        Returns:
            Dict containing PDF metadata
        """
        try:
            logger.debug(f"Getting metadata for file: {file_id}")
            
            temp_file = await self._download_file(file_id)
            if not temp_file:
                raise Exception("Failed to download file")
            
            doc = fitz.open(temp_file)
            metadata = doc.metadata
            
            # Add additional metadata
            metadata.update({
                "page_count": doc.page_count,
                "is_encrypted": doc.is_encrypted,
                "is_scanned": len(doc[0].get_text().strip()) == 0
            })
            
            doc.close()
            return metadata
            
        except Exception as e:
            logger.error(f"Error in get_pdf_metadata: {str(e)}")
            raise
        finally:
            await self._cleanup_temp_files()

    async def extract_images(self, file_id: str) -> List[Dict[str, Any]]:
        """
        Extract images from a PDF file.
        
        Args:
            file_id: Google Drive file ID
            
        Returns:
            List of dictionaries containing image data
        """
        try:
            logger.debug(f"Extracting images from file: {file_id}")
            
            temp_file = await self._download_file(file_id)
            if not temp_file:
                raise Exception("Failed to download file")
            
            doc = fitz.open(temp_file)
            images = []
            
            for page_num in range(doc.page_count):
                page = doc[page_num]
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    
                    images.append({
                        "page": page_num + 1,
                        "index": img_index,
                        "width": base_image["width"],
                        "height": base_image["height"],
                        "format": base_image["ext"],
                        "data": image_bytes
                    })
            
            doc.close()
            return images
            
        except Exception as e:
            logger.error(f"Error in extract_images: {str(e)}")
            raise
        finally:
            await self._cleanup_temp_files() 