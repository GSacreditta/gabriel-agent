from langchain.tools import BaseTool
from typing import Optional, Type, Dict, Any, Union
from pydantic import BaseModel, Field
from ..services.google_drive import GoogleDriveService
import logging
import json

logger = logging.getLogger(__name__)

class DriveToolInput(BaseModel):
    """Input for drive tool."""
    action: str = Field(..., description="The action to perform (list_files, get_folder_contents, etc.)")
    file_id: Optional[str] = Field(None, description="File ID for download or move operations")
    file_name: Optional[str] = Field(None, description="File name for search operations")
    folder_id: Optional[str] = Field(None, description="Folder ID for listing files or target folder for move")
    folder_name: Optional[str] = Field(None, description="Folder name for creation")

class DriveTool(BaseTool):
    """Tool for interacting with Google Drive files and folders."""
    
    name: str = "google_drive_tool"
    description: str = """Use this tool to interact with Google Drive files and folders.
    You can:
    - List files in a folder
    - Get contents of the main folder
    - Download and read files
    - Find files by name
    - Create new folders
    - Move files between folders
    
    Input should be a JSON string with the following format:
    {
        "action": "list_files" | "get_folder_contents" | "download_file" | "get_file_by_name" | "create_folder" | "move_file",
        "file_id": "optional file ID for download or move",
        "file_name": "optional file name for search",
        "folder_id": "optional folder ID for listing files or target folder for move",
        "folder_name": "optional folder name for creation"
    }
    """
    args_schema: Type[BaseModel] = DriveToolInput
    
    async def _arun(self, **kwargs) -> str:
        """Execute the tool asynchronously."""
        try:
            # Initialize the service
            service = GoogleDriveService()
            
            # Handle different actions
            action = kwargs.get('action')
            if action == 'list_files':
                # TODO: This method doesn't exist in GoogleDriveService
                # Consider using get_folder_contents() instead
                folder_id = kwargs.get('folder_id')
                files = await service.get_folder_contents()  # Using get_folder_contents as fallback
                return json.dumps(files, indent=2)
            elif action == 'get_folder_contents':
                files = await service.get_folder_contents()
                return json.dumps(files, indent=2)
            elif action == 'download_file':
                file_id = kwargs.get('file_id')
                if not file_id:
                    raise ValueError("file_id is required for download_file action")
                content = await service.download_file(file_id)
                return content.decode('utf-8') if isinstance(content, bytes) else str(content)
            elif action == 'get_file_by_name':
                # TODO: This method doesn't exist in GoogleDriveService
                # Consider implementing it or using a different approach
                file_name = kwargs.get('file_name')
                if not file_name:
                    raise ValueError("file_name is required for get_file_by_name action")
                folder_id = kwargs.get('folder_id')
                # For now, get all files and filter by name
                files = await service.get_folder_contents()
                matching_files = [f for f in files if f.get('name') == file_name]
                return json.dumps(matching_files[0] if matching_files else None, indent=2)
            elif action == 'create_folder':
                folder_name = kwargs.get('folder_name')
                if not folder_name:
                    raise ValueError("folder_name is required for create_folder action")
                parent_id = kwargs.get('folder_id')  # Optional parent folder ID
                folder = await service.create_folder(folder_name, parent_id)
                return json.dumps(folder, indent=2)
            elif action == 'move_file':
                # TODO: This method name doesn't match GoogleDriveService
                # Consider renaming to move_file_to_folder to match the service
                file_id = kwargs.get('file_id')
                folder_id = kwargs.get('folder_id')
                if not file_id:
                    raise ValueError("file_id is required for move_file action")
                if not folder_id:
                    raise ValueError("folder_id is required for move_file action")
                file = await service.move_file_to_folder(file_id, folder_id)  # Using correct method name
                return json.dumps(file, indent=2)
            else:
                raise ValueError(f"Unknown action: {action}")
                
        except Exception as e:
            logger.error(f"Error in DriveTool: {str(e)}")
            return f"Error: {str(e)}"
    
    def _run(self, **kwargs) -> str:
        """Execute the tool synchronously."""
        raise NotImplementedError("Drive tool does not support synchronous execution") 