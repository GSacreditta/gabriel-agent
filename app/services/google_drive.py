from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from ..core.config import get_settings
import logging
import io
import os
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
from typing import Optional, Dict, Any

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class GoogleDriveService:
    def __init__(self):
        try:
            self.settings = get_settings()
            logger.debug(f"Loading credentials from: {self.settings.get_google_credentials_path()}")
            
            # Initialize credentials with token refresh
            self.credentials = service_account.Credentials.from_service_account_file(
                self.settings.get_google_credentials_path(),
                scopes=['https://www.googleapis.com/auth/drive']
            )
            
            # Log service account details
            logger.info(f"Service Account Email: {self.credentials.service_account_email}")
            logger.info(f"Project ID: {self.credentials.project_id}")
            
            # Set token expiry to 55 minutes (5 minutes before the 60-minute limit)
            self.credentials.expiry = datetime.utcnow() + timedelta(minutes=55)
            
            logger.debug("Credentials loaded successfully")
            
            # Build the service with auto-refresh
            self.service = build('drive', 'v3', credentials=self.credentials)
            logger.debug("Drive service built successfully")
            
            # Store the last token refresh time
            self.last_refresh = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Error initializing GoogleDriveService: {str(e)}")
            raise

    async def cleanup(self):
        """Cleanup the service resources."""
        try:
            if hasattr(self, 'service') and self.service:
                # Close the service client
                if hasattr(self.service, '_http'):
                    self.service._http.close()
                self.service = None
            logger.info("Google Drive Service cleaned up successfully")
        except Exception as e:
            logger.warning(f"Error during Google Drive Service cleanup: {str(e)}")

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

    async def get_folder_contents(self):
        """Get contents of the authorized folder with token refresh."""
        try:
            # Ensure token is valid before making the request
            await self._ensure_valid_token()
            
            logger.info("=== Google Drive API Call Details ===")
            logger.info(f"Service Account File: {self.settings.get_google_credentials_path()}")
            logger.info(f"Service Account Email: {self.credentials.service_account_email}")
            logger.info(f"Project ID: {self.credentials.project_id}")
            logger.info(f"Folder ID: {self.settings.GOOGLE_DRIVE_FOLDER_ID}")
            
            def _list_files():
                # Log the exact API call parameters
                params = {
                    'q': f"'{self.settings.GOOGLE_DRIVE_FOLDER_ID}' in parents and trashed = false",
                    'spaces': 'drive',
                    'fields': 'nextPageToken, files(id, name, mimeType, createdTime, modifiedTime, size, webViewLink)',
                    'orderBy': 'modifiedTime desc',
                    'pageSize': 100
                }
                logger.info(f"API Call Parameters: {params}")
                
                results = self.service.files().list(**params).execute()
                
                files = results.get('files', [])
                logger.info(f"API Response: {results}")
                return files
            
            files = await asyncio.to_thread(_list_files)
            logger.info(f"Found {len(files)} files in master folder {self.settings.GOOGLE_DRIVE_FOLDER_ID}")
            
            if not files:
                logger.warning(f"No files found in folder {self.settings.GOOGLE_DRIVE_FOLDER_ID}. This could mean:")
                logger.warning("1. The folder is empty")
                logger.warning("2. The folder ID is incorrect")
                logger.warning("3. The service account doesn't have access to the folder")
            else:
                for file in files:
                    logger.info(f"File in master folder: {file['name']} (ID: {file['id']}, Type: {file.get('mimeType', 'unknown')})")
            
            return files
            
        except Exception as e:
            logger.error(f"Error getting folder contents: {str(e)}")
            logger.error(f"Full error details: {type(e).__name__}: {str(e)}")
            raise

    async def download_file(self, file_id: str) -> bytes:
        """Download a file from Google Drive."""
        try:
            # Ensure token is valid before making the request
            await self._ensure_valid_token()
            
            def _download():
                request = self.service.files().get_media(fileId=file_id)
                file = io.BytesIO()
                downloader = MediaIoBaseDownload(file, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                    logger.debug(f"Download {int(status.progress() * 100)}%")
                return file.getvalue()
            
            content = await asyncio.to_thread(_download)
            logger.debug(f"Successfully downloaded file {file_id}")
            return content
            
        except Exception as e:
            logger.error(f"Error downloading file: {str(e)}")
            raise

    async def create_folder(self, name: str, parent_id: str = None) -> dict:
        """Create a new folder in Google Drive with token refresh."""
        try:
            # Ensure token is valid before making the request
            await self._ensure_valid_token()
            
            # Use the main authorized folder if no parent_id is provided
            if not parent_id:
                parent_id = self.settings.GOOGLE_DRIVE_FOLDER_ID
            
            # Create folder metadata
            folder_metadata = {
                'name': name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }
            
            def _create_folder():
                folder = self.service.files().create(
                    body=folder_metadata,
                    fields='id, name, parents'
                ).execute()
                return folder
            
            folder = await asyncio.to_thread(_create_folder)
            logger.debug(f"Created folder: {name} with ID: {folder.get('id')}")
            return folder
            
        except Exception as e:
            logger.error(f"Error creating folder: {str(e)}")
            raise

    async def create_or_match_folder(self, name: str) -> dict:
        """Create or match a folder with token refresh."""
        try:
            # Ensure token is valid before making the request
            await self._ensure_valid_token()
            
            # First try to find an existing folder
            query = f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and '{self.settings.GOOGLE_DRIVE_FOLDER_ID}' in parents"
            
            def _find_folder():
                results = self.service.files().list(
                    q=query,
                    fields="files(id, name)"
                ).execute()
                files = results.get('files', [])
                return files[0] if files else None
            
            existing_folder = await asyncio.to_thread(_find_folder)
            
            if existing_folder:
                logger.info(f"Found existing folder: {name}")
                return {
                    "folder_id": existing_folder['id'],
                    "is_new": False
                }
            
            # Create new folder if not found
            folder = await self.create_folder(name)
            logger.info(f"Created new folder: {name}")
            return {
                "folder_id": folder['id'],
                "is_new": True
            }
            
        except Exception as e:
            logger.error(f"Error creating or matching folder: {str(e)}")
            raise

    async def move_file_to_folder(self, file_id: str, folder_id: str) -> dict:
        """Move a file to a specific folder with token refresh."""
        try:
            # Ensure token is valid before making the request
            await self._ensure_valid_token()
            
            def _move_file():
                # Get the current parents
                file = self.service.files().get(
                    fileId=file_id,
                    fields='parents'
                ).execute()
                
                # Remove from old parents and add to new parent
                previous_parents = ",".join(file.get('parents', []))
                file = self.service.files().update(
                    fileId=file_id,
                    addParents=folder_id,
                    removeParents=previous_parents,
                    fields='id, parents'
                ).execute()
                return file
            
            result = await asyncio.to_thread(_move_file)
            logger.debug(f"Moved file {file_id} to folder {folder_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error moving file to folder: {str(e)}")
            raise

    async def get_file_metadata(self, file_id: str) -> Dict[str, Any]:
        """Get file metadata.
        
        Args:
            file_id: File ID
            
        Returns:
            Dict containing file metadata
        """
        try:
            # Ensure token is valid before making the request
            await self._ensure_valid_token()
            
            def _get_metadata():
                return self.service.files().get(
                    fileId=file_id,
                    fields='id, name, mimeType, size, createdTime, modifiedTime'
                ).execute()
            
            metadata = await asyncio.to_thread(_get_metadata)
            logger.debug(f"Got metadata for file {file_id}: {metadata}")
            return metadata
            
        except Exception as e:
            logger.error(f"Error getting file metadata: {str(e)}")
            raise

    async def export_file(self, file_id: str, mime_type: str) -> bytes:
        """Export a Google Workspace file to a different format."""
        try:
            # Ensure token is valid before making the request
            await self._ensure_valid_token()
            
            def _export():
                request = self.service.files().export_media(
                    fileId=file_id,
                    mimeType=mime_type
                )
                file = io.BytesIO()
                downloader = MediaIoBaseDownload(file, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                    logger.debug(f"Export {int(status.progress() * 100)}%")
                return file.getvalue()
            
            content = await asyncio.to_thread(_export)
            logger.debug(f"Successfully exported file {file_id} to {mime_type}")
            return content
            
        except Exception as e:
            logger.error(f"Error exporting file: {str(e)}")
            raise

    async def get_specific_folder_contents(self, folder_id: str):
        """Get contents of a specific folder with token refresh."""
        try:
            # Ensure token is valid before making the request
            await self._ensure_valid_token()
            
            def _list_files():
                params = {
                    'q': f"'{folder_id}' in parents and trashed = false",
                    'spaces': 'drive',
                    'fields': 'nextPageToken, files(id, name, mimeType, createdTime, modifiedTime, size, webViewLink)',
                    'orderBy': 'modifiedTime desc',
                    'pageSize': 100
                }
                
                results = self.service.files().list(**params).execute()
                files = results.get('files', [])
                return files
            
            files = await asyncio.to_thread(_list_files)
            logger.info(f"Found {len(files)} files in folder {folder_id}")
            
            for file in files:
                logger.info(f"File in folder: {file['name']} (ID: {file['id']}, Type: {file.get('mimeType', 'unknown')})")
            
            return files
            
        except Exception as e:
            logger.error(f"Error getting folder contents: {str(e)}")
            raise

    async def move_file_to_master_folder(self, file_id: str) -> dict:
        """Move a file back to the master folder."""
        try:
            return await self.move_file_to_folder(file_id, self.settings.GOOGLE_DRIVE_FOLDER_ID)
        except Exception as e:
            logger.error(f"Error moving file to master folder: {str(e)}")
            raise

    async def download_file_to_temp(self, file_id: str) -> Optional[str]:
        """Download a file to a temporary location.
        
        Args:
            file_id: File ID
            
        Returns:
            Path to downloaded file
        """
        try:
            # Create temp directory if needed
            temp_dir = Path("temp")
            temp_dir.mkdir(exist_ok=True)
            
            # Download file
            content = await self.download_file(file_id)
            
            # Get file metadata for name
            metadata = await self.get_file_metadata(file_id)
            file_name = metadata.get("name", f"file_{file_id}")
            
            # Save to temp file
            temp_path = temp_dir / file_name
            temp_path.write_bytes(content)
            
            logger.info(f"Downloaded file to: {temp_path}")
            return str(temp_path)
            
        except Exception as e:
            logger.error(f"Error downloading file to temp: {str(e)}")
            raise 