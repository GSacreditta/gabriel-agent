from langchain.tools import BaseTool
from typing import Optional, Type, Dict, Any, List
from langchain_core.pydantic_v1 import BaseModel, Field
import json
import logging
from ..services.calendar_mcp import list_events, create_event

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class CalendarToolInput(BaseModel):
    """Input for calendar tool."""
    action: str = Field(..., description="The action to perform (list_events, create_event)")
    time_min: Optional[str] = Field(None, description="Start time for event listing (ISO format)")
    time_max: Optional[str] = Field(None, description="End time for event listing (ISO format)")
    summary: Optional[str] = Field(None, description="Event summary/title")
    start_time: Optional[str] = Field(None, description="Event start time (ISO format)")
    end_time: Optional[str] = Field(None, description="Event end time (ISO format)")
    description: Optional[str] = Field(None, description="Event description")
    location: Optional[str] = Field(None, description="Event location")
    attendees: Optional[List[str]] = Field(None, description="List of attendee email addresses")
    reminders: Optional[Dict[str, Any]] = Field(None, description="Event reminders configuration")
    calendar_id: Optional[str] = Field(None, description="Calendar ID to use (defaults to primary)")

class CalendarTool(BaseTool):
    """Tool for managing Google Calendar events."""
    
    name: str = Field(default="calendar_tool", description="The unique name of the tool that clearly communicates its purpose.")
    description: str = Field(default="""Use this tool to manage Google Calendar events.
    This tool can:
    1. List events in a time range
    2. Create new events
    
    Input should be a JSON string with the following format:
    {
        "action": "list_events" or "create_event",
        "time_min": "2024-01-01T00:00:00Z" (for list_events),
        "time_max": "2024-01-31T23:59:59Z" (for list_events),
        "summary": "Event title" (for create_event),
        "start_time": "2024-01-01T10:00:00Z" (for create_event),
        "end_time": "2024-01-01T11:00:00Z" (for create_event),
        "description": "Event description" (optional),
        "location": "Event location" (optional),
        "attendees": ["email@example.com"] (optional),
        "reminders": {"useDefault": true} (optional),
        "calendar_id": "primary" (optional)
    }
    """, description="Used to tell the model how/when/why to use the tool.")
    args_schema: Type[BaseModel] = CalendarToolInput
    
    async def _arun(self, **kwargs) -> str:
        """
        Run the calendar tool asynchronously.
        
        Args:
            **kwargs: The input parameters
            
        Returns:
            str: JSON string containing the operation results
        """
        try:
            action = kwargs.get('action')
            
            if action == 'list_events':
                time_min = kwargs.get('time_min')
                time_max = kwargs.get('time_max')
                calendar_id = kwargs.get('calendar_id', 'primary')
                
                events = await list_events(time_min, time_max, calendar_id)
                return str(events)
                
            elif action == 'create_event':
                event_details = {
                    'summary': kwargs.get('summary'),
                    'start': {'dateTime': kwargs.get('start_time')},
                    'end': {'dateTime': kwargs.get('end_time')},
                    'description': kwargs.get('description'),
                    'location': kwargs.get('location'),
                    'attendees': [{'email': email} for email in kwargs.get('attendees', [])],
                    'reminders': kwargs.get('reminders', {'useDefault': True})
                }
                calendar_id = kwargs.get('calendar_id', 'primary')
                
                event = await create_event(event_details, calendar_id)
                return str(event)
                
            else:
                raise ValueError(f"Invalid action: {action}")
                
        except Exception as e:
            logger.error(f"Error in calendar tool: {str(e)}")
            return f"Error: {str(e)}"
    
    def _run(self, **kwargs) -> str:
        """
        Run the calendar tool synchronously.
        This is a fallback method that should not be used.
        
        Args:
            **kwargs: The input parameters
            
        Returns:
            str: JSON string containing the operation results
        """
        raise NotImplementedError("Calendar tool does not support synchronous execution") 