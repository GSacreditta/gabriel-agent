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
            
            # Use Application Default Credentials for Cloud Run
            try:
                from google.auth import default
                self.credentials, project = default(scopes=['https://www.googleapis.com/auth/drive'])
                logger.info(f"Using Application Default Credentials for project: {project}")
            except Exception as adc_error:
                logger.warning(f"Application Default Credentials failed: {adc_error}")
                
                # Fallback to service account file for local development
                try:
                    logger.debug(f"Falling back to service account file: {self.settings.get_google_credentials_path()}")
                    self.credentials = service_account.Credentials.from_service_account_file(
                        self.settings.get_google_credentials_path(),
                        scopes=['https://www.googleapis.com/auth/drive']
                    )
                    logger.info("Service account file credentials loaded successfully")
                except Exception as file_error:
                    logger.error(f"Both ADC and service account file failed: ADC={adc_error}, File={file_error}")
                    raise ValueError("No valid Google Cloud credentials available")
            
            # Log authentication details
            if hasattr(self.credentials, 'service_account_email'):
                logger.info(f"Service Account Email: {self.credentials.service_account_email}")
            if hasattr(self.credentials, 'project_id'):
                logger.info(f"Project ID: {self.credentials.project_id}")
            
            logger.debug("Google Drive credentials loaded successfully")
            
            # Build the service - Google API client handles token refresh automatically
            self.service = build('drive', 'v3', credentials=self.credentials)
            logger.debug("Drive service built successfully")
            
            # Track initialization time for logging
            self.initialized_at = datetime.utcnow()
            
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

    async def get_folder_contents(self):
        """Get contents of the authorized folder.
        
        Service account credentials automatically handle token refresh,
        so no manual token management is needed.
        """
        try:
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
                
                # Google API client automatically handles token refresh if needed
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
        """Download a file from Google Drive.
        
        Service account credentials automatically handle token refresh.
        """
        try:
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

    async def create_folder(self, folder_name: str, parent_folder_id: str = None) -> str:
        """Create a new folder in Google Drive"""
        try:
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            if parent_folder_id:
                folder_metadata['parents'] = [parent_folder_id]
            
            # Create folder
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            folder_id = folder.get('id')
            logger.info(f"Created folder '{folder_name}' with ID: {folder_id}")
            
            return folder_id
            
        except Exception as e:
            logger.error(f"Error creating folder '{folder_name}': {str(e)}")
            return None

    async def move_file_to_folder(self, file_id: str, destination_folder_id: str) -> bool:
        """Move a file to a different folder"""
        try:
            # Get the file's current parents
            file_metadata = self.service.files().get(
                fileId=file_id,
                fields='parents'
            ).execute()
            
            previous_parents = ",".join(file_metadata.get('parents', []))
            
            # Move the file to the new folder
            file = self.service.files().update(
                fileId=file_id,
                addParents=destination_folder_id,
                removeParents=previous_parents,
                fields='id, parents'
            ).execute()
            
            logger.info(f"Moved file {file_id} to folder {destination_folder_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error moving file {file_id} to folder {destination_folder_id}: {str(e)}")
            return False

    async def get_folder_by_name(self, folder_name: str, parent_folder_id: str = None) -> str:
        """Find a folder by name, optionally within a parent folder"""
        try:
            query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder'"
            
            if parent_folder_id:
                query += f" and '{parent_folder_id}' in parents"
            
            results = self.service.files().list(
                q=query,
                fields='files(id, name)'
            ).execute()
            
            folders = results.get('files', [])
            
            if folders:
                folder_id = folders[0]['id']
                logger.info(f"Found folder '{folder_name}' with ID: {folder_id}")
                return folder_id
            else:
                logger.info(f"Folder '{folder_name}' not found")
                return None
                
        except Exception as e:
            logger.error(f"Error finding folder '{folder_name}': {str(e)}")
            return None

    async def create_or_match_folder(self, name: str) -> dict:
        """Create or match a folder.
        
        Service account credentials automatically handle token refresh.
        """
        try:
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

    async def get_file_metadata(self, file_id: str) -> Dict[str, Any]:
        """Get file metadata.
        
        Service account credentials automatically handle token refresh.
        
        Args:
            file_id: File ID
            
        Returns:
            Dict containing file metadata
        """
        try:
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
        """Export a Google Workspace file to a different format.
        
        Service account credentials automatically handle token refresh.
        """
        try:
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
        """Get contents of a specific folder.
        
        Service account credentials automatically handle token refresh.
        """
        try:
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