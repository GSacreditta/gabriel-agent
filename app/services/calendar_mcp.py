#!/usr/bin/env python
import os
import json
import sys
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format='DEBUG: %(asctime)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Load credentials from JSON file
CREDENTIALS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                               'config', 'credentials', 'location-19291-fb284eccae8d.json')

try:
    credentials = service_account.Credentials.from_service_account_file(
        CREDENTIALS_PATH,
        scopes=['https://www.googleapis.com/auth/calendar']
    )
    logger.debug('Service account credentials loaded successfully')
except Exception as e:
    logger.error(f"Error loading credentials from {CREDENTIALS_PATH}: {str(e)}")
    sys.exit(1)

async def list_events(
    time_min: str = None,
    time_max: str = None,
    max_results: int = 10,
    calendar_id: str = 'sternbergg@gmail.com'
) -> str:
    """List calendar events within a time range
    
    Args:
        time_min: Start time in ISO format (default: now)
        time_max: End time in ISO format (default: 7 days from now)
        max_results: Maximum number of events to return
        calendar_id: The calendar ID to list events from (default: sternbergg@gmail.com)
    
    Returns:
        String with formatted list of events
    """
    logger.debug(f'Listing calendar events with args: {locals()}')
    
    try:
        logger.debug('Creating calendar service')
        calendar_service = build('calendar', 'v3', credentials=credentials)
        logger.debug('Calendar service created')
        
        # Set default time range if not provided
        if not time_min:
            time_min = datetime.utcnow().isoformat() + 'Z'
        if not time_max:
            time_max = (datetime.utcnow() + timedelta(days=7)).isoformat() + 'Z'
            
        logger.debug(f'Fetching events from {time_min} to {time_max} for calendar {calendar_id}')
        events_result = calendar_service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        if not events:
            return 'No upcoming events found.'
            
        event_list = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            event_list.append(f"- {event['summary']} ({start} to {end})")
            
        return '\n'.join(event_list)
        
    except Exception as error:
        logger.debug(f'ERROR OCCURRED:')
        logger.debug(f'Error type: {type(error).__name__}')
        logger.debug(f'Error message: {str(error)}')
        import traceback
        logger.debug(f'Error traceback: {traceback.format_exc()}')
        raise Exception(f"Failed to list events: {str(error)}")

async def create_event(
    summary: str, 
    start_time: str, 
    end_time: str, 
    description: str = None, 
    location: str = None, 
    attendees: list = None, 
    reminders: dict = None,
    calendar_id: str = 'sternbergg@gmail.com'
) -> str:
    """Create a calendar event with specified details
    
    Args:
        summary: Event title
        start_time: Start time (ISO format)
        end_time: End time (ISO format)
        description: Event description
        location: Event location
        attendees: List of attendee emails
        reminders: Reminder settings for the event
        calendar_id: The calendar ID to create the event in (default: sternbergg@gmail.com)
    
    Returns:
        String with event creation confirmation and link
    """
    logger.debug(f'Creating calendar event with args: {locals()}')
    
    try:
        logger.debug('Creating calendar service')
        calendar_service = build('calendar', 'v3', credentials=credentials)
        logger.debug('Calendar service created')
        
        event = {
            'summary': summary,
            'start': {
                'dateTime': start_time,
                'timeZone': 'Asia/Seoul'
            },
            'end': {
                'dateTime': end_time,
                'timeZone': 'Asia/Seoul'
            }
        }
        
        if description:
            event['description'] = description
        
        if location:
            event['location'] = location
            logger.debug(f'Location added: {location}')
        
        if attendees:
            event['attendees'] = [{'email': email} for email in attendees]
            logger.debug(f'Attendees added: {event["attendees"]}')
        
        if reminders:
            event['reminders'] = reminders
            logger.debug(f'Custom reminders set: {json.dumps(reminders)}')
        else:
            event['reminders'] = {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': 10}
                ]
            }
            logger.debug(f'Default reminders set: {json.dumps(event["reminders"])}')
        
        logger.debug(f'Attempting to insert event into calendar {calendar_id}')
        response = calendar_service.events().insert(calendarId=calendar_id, body=event).execute()
        logger.debug(f'Event insert response: {json.dumps(response)}')
        
        return f"Event created: {response.get('htmlLink', 'No link available')}"
        
    except Exception as error:
        logger.debug(f'ERROR OCCURRED:')
        logger.debug(f'Error type: {type(error).__name__}')
        logger.debug(f'Error message: {str(error)}')
        import traceback
        logger.debug(f'Error traceback: {traceback.format_exc()}')
        raise Exception(f"Failed to create event: {str(error)}")