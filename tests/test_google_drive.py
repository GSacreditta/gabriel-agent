import pytest
from app.services.google_drive import GoogleDriveService
import asyncio

@pytest.mark.asyncio
async def test_google_drive_access():
    """Test basic Google Drive access by listing folder contents."""
    try:
        # Initialize the service
        drive_service = GoogleDriveService()
        
        # Get folder contents
        files = await drive_service.get_folder_contents()
        
        # Basic validation
        assert isinstance(files, list), "Should return a list of files"
        
        # Print some basic info about the files
        print(f"\nFound {len(files)} files in the folder:")
        for file in files:
            print(f"- {file['name']} (ID: {file['id']}, Type: {file['mimeType']})")
            
    except Exception as e:
        pytest.fail(f"Failed to access Google Drive: {str(e)}") 