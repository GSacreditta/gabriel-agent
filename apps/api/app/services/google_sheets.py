from google.oauth2 import service_account
from googleapiclient.discovery import build
from ..core.config import get_settings
import logging
from typing import List, Dict, Any, Optional

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class GoogleSheetsService:
    def __init__(self):
        try:
            self.settings = get_settings()
            logger.debug(f"Loading credentials from: {self.settings.get_google_credentials_path()}")
            
            # Use the same credentials as Google Drive service
            self.credentials = service_account.Credentials.from_service_account_file(
                self.settings.get_google_credentials_path(),
                scopes=[
                    'https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive'  # Keep Drive scope for file operations
                ]
            )
            logger.debug("Credentials loaded successfully")
            
            self.service = build('sheets', 'v4', credentials=self.credentials)
            logger.debug("Sheets service built successfully")
        except Exception as e:
            logger.error(f"Error initializing GoogleSheetsService: {str(e)}")
            raise

    def read_sheet(self, spreadsheet_id: str, range_name: str) -> List[List[Any]]:
        """
        Read data from a Google Sheet.
        
        Args:
            spreadsheet_id: The ID of the spreadsheet
            range_name: The range to read (e.g., 'Sheet1!A1:D10')
            
        Returns:
            List of rows containing the data
        """
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            logger.debug(f"Read {len(values)} rows from sheet")
            return values
        except Exception as e:
            logger.error(f"Error reading sheet: {str(e)}")
            raise

    def write_sheet(self, spreadsheet_id: str, range_name: str, values: List[List[Any]]) -> Dict[str, Any]:
        """
        Write data to a Google Sheet.
        
        Args:
            spreadsheet_id: The ID of the spreadsheet
            range_name: The range to write to (e.g., 'Sheet1!A1')
            values: The data to write
            
        Returns:
            The response from the API
        """
        try:
            body = {
                'values': values
            }
            
            result = self.service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                body=body
            ).execute()
            
            logger.debug(f"Updated {result.get('updatedCells')} cells")
            return result
        except Exception as e:
            logger.error(f"Error writing to sheet: {str(e)}")
            raise

    def append_to_sheet(self, spreadsheet_id: str, range_name: str, values: List[List[Any]]) -> Dict[str, Any]:
        """
        Append data to a Google Sheet.
        
        Args:
            spreadsheet_id: The ID of the spreadsheet
            range_name: The range to append to (e.g., 'Sheet1!A:A')
            values: The data to append
            
        Returns:
            The response from the API
        """
        try:
            body = {
                'values': values
            }
            
            result = self.service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
            logger.debug(f"Appended {len(values)} rows")
            return result
        except Exception as e:
            logger.error(f"Error appending to sheet: {str(e)}")
            raise

    def create_sheet(self, title: str) -> Dict[str, Any]:
        """
        Create a new Google Sheet in the authorized folder.
        
        Args:
            title: The title of the new spreadsheet
            
        Returns:
            The created spreadsheet's metadata
        """
        try:
            # First create the spreadsheet
            spreadsheet = {
                'properties': {
                    'title': title
                }
            }
            
            result = self.service.spreadsheets().create(body=spreadsheet).execute()
            spreadsheet_id = result.get('spreadsheetId')
            logger.debug(f"Created new spreadsheet: {spreadsheet_id}")
            
            # Now move it to the authorized folder
            drive_service = build('drive', 'v3', credentials=self.credentials)
            file = drive_service.files().update(
                fileId=spreadsheet_id,
                addParents=self.settings.GOOGLE_DRIVE_FOLDER_ID,
                fields='id, parents'
            ).execute()
            
            logger.debug(f"Moved spreadsheet to authorized folder: {self.settings.GOOGLE_DRIVE_FOLDER_ID}")
            return result
        except Exception as e:
            logger.error(f"Error creating sheet: {str(e)}")
            raise 