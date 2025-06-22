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
from langchain_community.document_loaders import (
    PyPDFLoader,
    PDFMinerLoader,
    PyMuPDFLoader,
    UnstructuredPDFLoader,
)
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
    """Service for processing PDF documents with multiple parsing strategies."""

    def __init__(self):
        """Initialize the PDF service with available parsers."""
        self.parsers = [
            ("pymupdf", PyMuPDFLoader),
            ("pypdf", PyPDFLoader),
            ("pdfminer", PDFMinerLoader),
            ("unstructured", UnstructuredPDFLoader),
        ]
        logger.info("PDF Service initialized with multiple parsing strategies")
    
    async def extract_text(self, file_path: str) -> Dict[str, Any]:
        """Extract text from a PDF using multiple parsing strategies.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Dict containing:
                - success: bool indicating if extraction was successful
                - text: extracted text if successful
                - parser_used: name of the successful parser
                - error: error message if unsuccessful
        """
        for parser_name, parser_class in self.parsers:
            try:
                logger.info(f"Attempting PDF extraction with {parser_name}")
                loader = parser_class(file_path)
                
                # Handle different return types from parsers
                documents = loader.load()
                
                if not documents:
                    logger.warning(f"{parser_name} extracted no text")
                    continue
                
                # Combine text from all pages
                text = "\n".join(doc.page_content for doc in documents)
                
                if not text.strip():
                    logger.warning(f"{parser_name} extracted empty text")
                    continue
                
                logger.info(f"Successfully extracted text using {parser_name}")
                return {
                    "success": True,
                    "text": text,
                    "parser_used": parser_name,
                    "metadata": {
                        "page_count": len(documents),
                        "char_count": len(text)
                    }
                }
                
            except Exception as e:
                logger.warning(f"Parser {parser_name} failed: {str(e)}")
                continue
        
        logger.error("All PDF parsing strategies failed")
        return {
            "success": False,
            "error": "Failed to extract text with all available parsers",
            "parser_used": None
        }
    
    async def get_page_count(self, file_path: str) -> int:
        """Get the number of pages in a PDF.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Number of pages in the PDF
        """
        try:
            doc = fitz.open(file_path)
            page_count = len(doc)
            doc.close()
            return page_count
        except Exception as e:
            logger.error(f"Error getting page count: {str(e)}")
            return 0
    
    async def extract_images(self, file_path: str) -> Dict[str, Any]:
        """Extract images from a PDF file.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Dict containing extracted images and their metadata
        """
        try:
            doc = fitz.open(file_path)
            images = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    
                    if base_image:
                        images.append({
                            "page": page_num + 1,
                            "index": img_index + 1,
                            "image": base_image["image"],
                            "ext": base_image["ext"],
                            "size": len(base_image["image"])
                        })
            
            doc.close()
            return {
                "success": True,
                "images": images,
                "total_images": len(images)
            }
            
        except Exception as e:
            logger.error(f"Error extracting images: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _validate_pdf(self, file_path: str) -> Dict[str, Any]:
        """Validate a PDF file and extract metadata.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Dict containing validation results and metadata
        """
        try:
            # Check if file exists
            if not Path(file_path).exists():
                return {
                    "is_valid": False,
                    "error": "File not found"
                }
            
            # Try to open with PyMuPDF
            doc = fitz.open(file_path)
            try:
                metadata = doc.metadata
                page_count = len(doc)
                
                if page_count == 0:
                    return {
                        "is_valid": False,
                        "error": "PDF has no pages"
                    }
                
                return {
                    "is_valid": True,
                    "page_count": page_count,
                    "metadata": metadata
                }
                
            finally:
                doc.close()
                
        except Exception as e:
            logger.error(f"Error validating PDF: {str(e)}")
            return {
                "is_valid": False,
                "error": str(e)
            }

    def _check_if_scanned(self, file_path: str) -> bool:
        """Check if a PDF appears to be scanned.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            True if the PDF appears to be scanned, False otherwise
        """
        try:
            doc = fitz.open(file_path)
            try:
                # Check first few pages
                for page_num in range(min(3, len(doc))):
                    page = doc[page_num]
                    
                    # Get text and images
                    text = page.get_text()
                    images = page.get_images()
                    
                    # If page has no text but has images, likely scanned
                    if not text.strip() and images:
                        return True
                        
                return False
                
            finally:
                doc.close()
                
        except Exception as e:
            logger.warning(f"Error checking if PDF is scanned: {str(e)}")
            return False

    def __del__(self):
        """Cleanup temporary directory on object destruction."""
        try:
            if hasattr(self, 'temp_dir') and self.temp_dir.exists():
                import shutil
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temp directory: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp directory: {str(e)}")

    async def _extract_text(self, file_path: str, mime_type: str) -> Dict[str, Any]:
        """Extract text from a document using appropriate service.
        
        Workflow:
        1. For PDFs:
           - Try PDF service first (uses multiple parsers)
           - Only use OCR if PDF service fails or detects scanned document
        2. For non-PDFs:
           - Use OCR service directly
        """
        # Implementation of the method
        pass 