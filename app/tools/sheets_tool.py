from langchain.tools import BaseTool
from typing import Optional, Type, List, Any
from pydantic import BaseModel, Field
from ..services.google_sheets import GoogleSheetsService

class ReadSheetInput(BaseModel):
    spreadsheet_id: str = Field(..., description="The ID of the Google Sheet to read from")
    range_name: str = Field(..., description="The range to read (e.g., 'Sheet1!A1:D10')")

class WriteSheetInput(BaseModel):
    spreadsheet_id: str = Field(..., description="The ID of the Google Sheet to write to")
    range_name: str = Field(..., description="The range to write to (e.g., 'Sheet1!A1')")
    values: List[List[Any]] = Field(..., description="The data to write (list of lists)")

class AppendSheetInput(BaseModel):
    spreadsheet_id: str = Field(..., description="The ID of the Google Sheet to append to")
    range_name: str = Field(..., description="The range to append to (e.g., 'Sheet1!A:A')")
    values: List[List[Any]] = Field(..., description="The data to append (list of lists)")

class CreateSheetInput(BaseModel):
    title: str = Field(..., description="The title of the new spreadsheet")

class ReadSheetTool(BaseTool):
    """Tool for reading data from Google Sheets."""
    
    name: str = "read_sheet"
    description: str = "Read data from a Google Sheet"
    args_schema: Type[BaseModel] = ReadSheetInput
    
    async def _arun(self, **kwargs) -> str:
        sheets_service = GoogleSheetsService()
        try:
            values = sheets_service.read_sheet(kwargs['spreadsheet_id'], kwargs['range_name'])
            return f"Successfully read {len(values)} rows from sheet"
        except Exception as e:
            return f"Error reading sheet: {str(e)}"
    
    def _run(self, **kwargs) -> str:
        raise NotImplementedError("Read sheet tool does not support synchronous execution")

class WriteSheetTool(BaseTool):
    """Tool for writing data to Google Sheets."""
    
    name: str = "write_sheet"
    description: str = "Write data to a Google Sheet"
    args_schema: Type[BaseModel] = WriteSheetInput
    
    async def _arun(self, **kwargs) -> str:
        sheets_service = GoogleSheetsService()
        try:
            result = sheets_service.write_sheet(
                kwargs['spreadsheet_id'],
                kwargs['range_name'],
                kwargs['values']
            )
            return f"Successfully updated {result.get('updatedCells')} cells"
        except Exception as e:
            return f"Error writing to sheet: {str(e)}"
    
    def _run(self, **kwargs) -> str:
        raise NotImplementedError("Write sheet tool does not support synchronous execution")

class AppendSheetTool(BaseTool):
    """Tool for appending data to Google Sheets."""
    
    name: str = "append_sheet"
    description: str = "Append data to a Google Sheet"
    args_schema: Type[BaseModel] = AppendSheetInput
    
    async def _arun(self, **kwargs) -> str:
        sheets_service = GoogleSheetsService()
        try:
            result = sheets_service.append_to_sheet(
                kwargs['spreadsheet_id'],
                kwargs['range_name'],
                kwargs['values']
            )
            return f"Successfully appended {len(kwargs['values'])} rows"
        except Exception as e:
            return f"Error appending to sheet: {str(e)}"
    
    def _run(self, **kwargs) -> str:
        raise NotImplementedError("Append sheet tool does not support synchronous execution")

class CreateSheetTool(BaseTool):
    """Tool for creating new Google Sheets."""
    
    name: str = "create_sheet"
    description: str = "Create a new Google Sheet"
    args_schema: Type[BaseModel] = CreateSheetInput
    
    async def _arun(self, **kwargs) -> str:
        sheets_service = GoogleSheetsService()
        try:
            result = sheets_service.create_sheet(kwargs['title'])
            return f"Successfully created new spreadsheet with ID: {result.get('spreadsheetId')}"
        except Exception as e:
            return f"Error creating sheet: {str(e)}"
    
    def _run(self, **kwargs) -> str:
        raise NotImplementedError("Create sheet tool does not support synchronous execution") 