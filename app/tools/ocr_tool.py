from langchain.tools import BaseTool
from typing import Optional, Type, Dict, Any
from pydantic import BaseModel, Field
import json
import logging
from ..services.ocr_service import OCRService

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class OCRToolInput(BaseModel):
    """Input for OCR tool."""
    file_id: str = Field(..., description="The Google Drive file ID to process")
    extract_structured: bool = Field(
        default=False,
        description="Whether to extract structured data from the document"
    )

class OCRTool(BaseTool):
    """Tool for performing OCR on documents."""
    
    name: str = "ocr_tool"
    description: str = """Use this tool to extract text from documents.
    This tool can:
    1. Extract raw text from documents
    2. Extract structured data (when available)
    
    Input should be a JSON string with the following format:
    {
        "file_id": "Google Drive file ID to process",
        "extract_structured": true/false (optional, defaults to false)
    }
    """
    args_schema: Type[BaseModel] = OCRToolInput
    
    def __init__(self):
        """Initialize the OCR tool with OCR service."""
        super().__init__()
        object.__setattr__(self, '_ocr_service', OCRService())
    
    async def _arun(self, **kwargs) -> str:
        """
        Run the OCR tool asynchronously.
        
        Args:
            **kwargs: The input parameters
            
        Returns:
            str: JSON string containing the processing results
        """
        try:
            file_id = kwargs['file_id']
            extract_structured = kwargs.get('extract_structured', False)
            
            logger.debug(f"Starting OCR processing for file: {file_id}")
            
            if extract_structured:
                result = await self._ocr_service.process_document(file_id)
            else:
                result = await self._ocr_service.extract_text(file_id)
            
            return json.dumps(result)
            
        except Exception as e:
            logger.error(f"Error in OCR tool: {str(e)}")
            return json.dumps({
                "success": False,
                "error": str(e),
                "file_id": kwargs.get('file_id', 'unknown')
            })
    
    def _run(self, **kwargs) -> str:
        """
        Run the OCR tool synchronously.
        This is a fallback method that should not be used.
        
        Args:
            **kwargs: The input parameters
            
        Returns:
            str: JSON string containing the processing results
        """
        raise NotImplementedError("OCR tool does not support synchronous execution") 