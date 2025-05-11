from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from ..core.config import get_settings
import logging
import io
import os

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class GoogleDriveService:
    def __init__(self):
        try:
            self.settings = get_settings()
            logger.debug(f"Loading credentials from: {self.settings.get_google_credentials_path()}")
            
            # Read and log the first few characters of the credentials file (safely)
            with open(self.settings.get_google_credentials_path(), 'r') as f:
                creds_content = f.read()
                logger.debug(f"Credentials file starts with: {creds_content[:50]}...")
            
            self.credentials = service_account.Credentials.from_service_account_file(
                self.settings.get_google_credentials_path(),
                scopes=['https://www.googleapis.com/auth/drive']
            )
            logger.debug("Credentials loaded successfully")
            
            self.service = build('drive', 'v3', credentials=self.credentials)
            logger.debug("Drive service built successfully")
        except Exception as e:
            logger.error(f"Error initializing GoogleDriveService: {str(e)}")
            raise

    def list_files(self, folder_id: str = None):
        """List files in the specified folder or root if no folder_id provided."""
        try:
            query = f"'{folder_id}' in parents" if folder_id else None
            logger.debug(f"Querying files with query: {query}")
            
            results = self.service.files().list(
                q=query,
                pageSize=10,
                fields="nextPageToken, files(id, name, mimeType)"
            ).execute()
            
            files = results.get('files', [])
            logger.debug(f"Found {len(files)} files")
            return files
        except Exception as e:
            logger.error(f"Error listing files: {str(e)}")
            raise

    def get_folder_contents(self):
        """Get contents of the main SM18_FO folder."""
        try:
            logger.debug(f"Getting contents of folder: {self.settings.GOOGLE_DRIVE_FOLDER_ID}")
            return self.list_files(self.settings.GOOGLE_DRIVE_FOLDER_ID)
        except Exception as e:
            logger.error(f"Error getting folder contents: {str(e)}")
            raise

    def download_file(self, file_id: str) -> str:
        """Download a file from Google Drive and return its contents as a string."""
        try:
            logger.debug(f"Downloading file with ID: {file_id}")
            
            # Get file metadata
            file_metadata = self.service.files().get(fileId=file_id, fields='mimeType,name').execute()
            mime_type = file_metadata.get('mimeType', '')
            file_name = file_metadata.get('name', '')
            
            # Handle different file types
            if 'google-apps' in mime_type:
                # For Google Docs, Sheets, etc.
                if 'document' in mime_type:
                    return self.service.files().export(fileId=file_id, mimeType='text/plain').execute().decode('utf-8')
                elif 'spreadsheet' in mime_type:
                    return self.service.files().export(fileId=file_id, mimeType='text/csv').execute().decode('utf-8')
            elif 'pdf' in mime_type.lower():
                # For PDF files, return metadata and a message
                return f"PDF file: {file_name}\nThis is a PDF file and cannot be read directly. Please use a PDF reader to view its contents."
            else:
                # For regular text files
                request = self.service.files().get_media(fileId=file_id)
                file = io.BytesIO()
                downloader = MediaIoBaseDownload(file, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                    logger.debug(f"Download {int(status.progress() * 100)}%")
                
                try:
                    return file.getvalue().decode('utf-8')
                except UnicodeDecodeError:
                    return f"Binary file: {file_name}\nThis file contains binary data and cannot be read as text."
                
        except Exception as e:
            logger.error(f"Error downloading file: {str(e)}")
            raise

    def get_file_by_name(self, name: str, folder_id: str = None) -> dict:
        """Find a file by name in the specified folder or root."""
        try:
            query = f"name = '{name}'"
            if folder_id:
                query += f" and '{folder_id}' in parents"
            
            results = self.service.files().list(
                q=query,
                fields="files(id, name, mimeType)"
            ).execute()
            
            files = results.get('files', [])
            if files:
                return files[0]
            return None
        except Exception as e:
            logger.error(f"Error finding file: {str(e)}")
            raise

    def create_folder(self, name: str, parent_id: str = None) -> dict:
        """
        Create a new folder in Google Drive.
        
        Args:
            name: The name of the folder to create
            parent_id: The ID of the parent folder (defaults to the main authorized folder)
            
        Returns:
            The created folder's metadata
        """
        try:
            # Use the main authorized folder if no parent_id is provided
            if not parent_id:
                parent_id = self.settings.GOOGLE_DRIVE_FOLDER_ID
            
            # Create folder metadata
            folder_metadata = {
                'name': name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }
            
            # Create the folder
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id, name, parents'
            ).execute()
            
            logger.debug(f"Created folder: {name} with ID: {folder.get('id')}")
            return folder
        except Exception as e:
            logger.error(f"Error creating folder: {str(e)}")
            raise

    def move_file(self, file_id: str, new_parent_id: str) -> dict:
        """
        Move a file to a new parent folder.
        
        Args:
            file_id: The ID of the file to move
            new_parent_id: The ID of the new parent folder
            
        Returns:
            The updated file metadata
        """
        try:
            # First, get the current parents of the file
            file = self.service.files().get(
                fileId=file_id,
                fields='parents'
            ).execute()
            
            previous_parents = ",".join(file.get('parents', []))
            
            # Move the file to the new parent
            file = self.service.files().update(
                fileId=file_id,
                addParents=new_parent_id,
                removeParents=previous_parents,
                fields='id, name, parents'
            ).execute()
            
            logger.debug(f"Moved file {file.get('name')} to folder {new_parent_id}")
            return file
            
        except Exception as e:
            logger.error(f"Error moving file: {str(e)}")
            raise 