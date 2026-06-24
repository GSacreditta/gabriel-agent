from langchain.tools import BaseTool
from typing import Optional, Type
from pydantic import BaseModel, Field
from ..services.google_drive import GoogleDriveService
import logging

logger = logging.getLogger(__name__)

class DocumentToolInput(BaseModel):
    """Input for document tool."""
    document_name: str = Field(..., description="The name of the document to read from Google Drive")

class DocumentTool(BaseTool):
    """Tool for reading and summarizing documents from Google Drive."""
    
    name: str = "read_document"
    description: str = "Read and summarize a document from Google Drive. Input should be the name of the document."
    args_schema: Type[BaseModel] = DocumentToolInput

    async def _arun(self, **kwargs) -> str:
        """Read and summarize a document from Google Drive asynchronously."""
        try:
            # Initialize Google Drive service
            drive_service = GoogleDriveService()
            
            # Find the document
            file = drive_service.get_file_by_name(kwargs['document_name'])
            if not file:
                return f"Document '{kwargs['document_name']}' not found in Google Drive."
            
            # Download and read the document
            content = drive_service.download_file(file['id'])
            
            # Return the content for the agent to summarize
            return f"Document content:\n\n{content}"
            
        except Exception as e:
            logger.error(f"Error reading document: {str(e)}")
            return f"Error reading document: {str(e)}"
    
    def _run(self, **kwargs) -> str:
        """Read and summarize a document from Google Drive synchronously."""
        raise NotImplementedError("Document tool does not support synchronous execution") 