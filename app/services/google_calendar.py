from google.oauth2 import service_account
from googleapiclient.discovery import build
from ..core.config import get_settings
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class GoogleCalendarService:
    def __init__(self):
        try:
            self.settings = get_settings()
            logger.debug(f"Loading credentials from: {self.settings.get_google_credentials_path()}")
            
            self.credentials = service_account.Credentials.from_service_account_file(
                self.settings.get_google_credentials_path(),
                scopes=['https://www.googleapis.com/auth/calendar']
            )
            logger.debug("Credentials loaded successfully")
            
            self.service = build('calendar', 'v3', credentials=self.credentials)
            logger.debug("Calendar service built successfully")
        except Exception as e:
            logger.error(f"Error initializing GoogleCalendarService: {str(e)}")
            raise

    def list_events(self, max_results: int = 10, time_min: str = None) -> List[Dict[str, Any]]:
        """
        List upcoming events from the calendar.
        
        Args:
            max_results: Maximum number of events to return
            time_min: Start time for the events (ISO format)
            
        Returns:
            List of event dictionaries
        """
        try:
            if not time_min:
                time_min = datetime.utcnow().isoformat() + 'Z'
            
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=time_min,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            logger.debug(f"Found {len(events)} events")
            return events
        except Exception as e:
            logger.error(f"Error listing events: {str(e)}")
            raise

    def get_event(self, event_id: str) -> Dict[str, Any]:
        """
        Get details of a specific event.
        
        Args:
            event_id: The ID of the event to retrieve
            
        Returns:
            Event details as a dictionary
        """
        try:
            event = self.service.events().get(
                calendarId='primary',
                eventId=event_id
            ).execute()
            
            logger.debug(f"Retrieved event: {event.get('summary')}")
            return event
        except Exception as e:
            logger.error(f"Error getting event: {str(e)}")
            raise

    def create_event(self, summary: str, start_time: str, end_time: str, 
                    description: str = None, location: str = None,
                    attendees: List[str] = None, reminders: Dict = None) -> Dict[str, Any]:
        """
        Create a new calendar event.
        
        Args:
            summary: Event title
            start_time: Start time (ISO format)
            end_time: End time (ISO format)
            description: Event description
            location: Event location
            attendees: List of attendee emails
            reminders: Reminder settings
            
        Returns:
            Created event details
        """
        try:
            event = {
                'summary': summary,
                'start': {
                    'dateTime': start_time,
                    'timeZone': 'UTC'
                },
                'end': {
                    'dateTime': end_time,
                    'timeZone': 'UTC'
                }
            }
            
            if description:
                event['description'] = description
            
            if location:
                event['location'] = location
            
            if attendees:
                event['attendees'] = [{'email': email} for email in attendees]
            
            if reminders:
                event['reminders'] = reminders
            else:
                event['reminders'] = {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'popup', 'minutes': 10}
                    ]
                }
            
            created_event = self.service.events().insert(
                calendarId='primary',
                body=event,
                sendUpdates='all'
            ).execute()
            
            logger.debug(f"Created event: {created_event.get('summary')}")
            return created_event
        except Exception as e:
            logger.error(f"Error creating event: {str(e)}")
            raise

    def update_event(self, event_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing calendar event.
        
        Args:
            event_id: The ID of the event to update
            updates: Dictionary of fields to update
            
        Returns:
            Updated event details
        """
        try:
            # First get the existing event
            event = self.get_event(event_id)
            
            # Update the fields
            for key, value in updates.items():
                if key in ['start', 'end']:
                    event[key] = {
                        'dateTime': value,
                        'timeZone': 'UTC'
                    }
                else:
                    event[key] = value
            
            updated_event = self.service.events().update(
                calendarId='primary',
                eventId=event_id,
                body=event,
                sendUpdates='all'
            ).execute()
            
            logger.debug(f"Updated event: {updated_event.get('summary')}")
            return updated_event
        except Exception as e:
            logger.error(f"Error updating event: {str(e)}")
            raise

    def delete_event(self, event_id: str) -> None:
        """
        Delete a calendar event.
        
        Args:
            event_id: The ID of the event to delete
        """
        try:
            self.service.events().delete(
                calendarId='primary',
                eventId=event_id,
                sendUpdates='all'
            ).execute()
            
            logger.debug(f"Deleted event with ID: {event_id}")
        except Exception as e:
            logger.error(f"Error deleting event: {str(e)}")
            raise

    def get_upcoming_notifications(self, hours_ahead: int = 24) -> List[Dict[str, Any]]:
        """
        Get events that have upcoming notifications.
        
        Args:
            hours_ahead: Number of hours to look ahead for notifications
            
        Returns:
            List of events with upcoming notifications
        """
        try:
            now = datetime.utcnow()
            time_min = now.isoformat() + 'Z'
            time_max = (now + timedelta(hours=hours_ahead)).isoformat() + 'Z'
            
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            notifications = []
            
            for event in events:
                start = datetime.fromisoformat(event['start'].get('dateTime', '').replace('Z', '+00:00'))
                time_until = start - now
                
                # Check if event has reminders
                reminders = event.get('reminders', {}).get('overrides', [])
                for reminder in reminders:
                    if reminder.get('method') == 'popup':
                        minutes = reminder.get('minutes', 0)
                        if 0 <= time_until.total_seconds() / 60 <= minutes:
                            notifications.append({
                                'event': event,
                                'minutes_until': minutes,
                                'notification_time': start - timedelta(minutes=minutes)
                            })
            
            logger.debug(f"Found {len(notifications)} upcoming notifications")
            return notifications
        except Exception as e:
            logger.error(f"Error getting notifications: {str(e)}")
            raise 