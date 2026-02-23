"""
Email Scanning Service - Monitors Gmail inbox for documents with intelligent filtering
"""

import logging
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
import re
import hashlib
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
import tempfile
import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

class EmailScanningService:
    """Service for scanning Gmail inbox and processing documents via email."""
    
    def __init__(self):
        self.settings = get_settings()
        self.gmail_service = None
        self.agent_coordinator = None
        self.drive_service = None
        self.vector_service = None
        
        # Gmail API scopes
        self.SCOPES = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.modify',
            'https://www.googleapis.com/auth/gmail.send'
        ]
        
        # Processing configuration
        self.scan_interval_minutes = 15
        self.business_hours = {
            'start': 8,  # 8 AM EST
            'end': 18,   # 6 PM EST
            'timezone': 'US/Eastern'
        }
        
        # Email filtering patterns (configurable)
        self.approved_senders = [
            "@trustedpartner.com",
            "@clientcompany.com", 
            "documents@yourcompany.com",
            # Add your actual sender patterns here
        ]
        
        self.subject_patterns = [
            r"document.*review",
            r"urgent.*review", 
            r"financial.*report",
            r"contract.*approval",
            r"invoice.*processing",
            r"\.pdf$|\.docx?$|\.xlsx?$",  # Subject mentions file extensions
        ]
        
        # Gmail labels for organization
        self.labels = {
            'processed': 'Gabriel/Processed',
            'pending': 'Gabriel/Pending',
            'duplicates': 'Gabriel/Duplicates',
            'errors': 'Gabriel/Errors'
        }
        
        # Duplicate detection cache
        self.processed_attachments = {}
        
    async def initialize(self, agent_coordinator=None, drive_service=None, vector_service=None):
        """Initialize the email scanning service with dependencies."""
        try:
            self.agent_coordinator = agent_coordinator
            self.drive_service = drive_service
            self.vector_service = vector_service
            
            # Ensure credentials directory exists
            credentials_dir = os.getenv('GMAIL_CREDENTIALS_DIR', 'config/credentials')
            os.makedirs(credentials_dir, exist_ok=True)
            
            # Authenticate with Gmail
            await self._authenticate_gmail()
            
            # Create Gmail labels if they don't exist
            await self._setup_gmail_labels()
            
            logger.info("✅ Email Scanning Service initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Email Scanning Service: {e}")
            return False
    
    async def _authenticate_gmail(self):
        """Authenticate with Gmail API using OAuth2."""
        try:
            creds = None
            credentials_dir = os.getenv('GMAIL_CREDENTIALS_DIR', 'config/credentials')
            token_file = os.path.join(credentials_dir, 'gmail_token.json')
            
            # Get OAuth credentials from environment variables
            client_id = os.getenv('GMAIL_CLIENT_ID')
            client_secret = os.getenv('GMAIL_CLIENT_SECRET')
            
            logger.info(f"🔑 Authenticating Gmail API...")
            logger.info(f"   📁 Token file: {token_file}")
            logger.info(f"   🆔 Client ID: {client_id[:20]}..." if client_id else "   ❌ No Client ID found")
            
            if not client_id or not client_secret:
                raise ValueError(
                    "Gmail OAuth credentials not found in environment variables.\n"
                    "Please set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in your .env file"
                )
            
            # Load existing token
            if os.path.exists(token_file):
                logger.info("📄 Loading existing Gmail token...")
                creds = Credentials.from_authorized_user_file(token_file, self.SCOPES)
            
            # If no valid credentials, go through OAuth flow
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    logger.info("🔄 Refreshing expired Gmail token...")
                    creds.refresh(Request())
                else:
                    logger.info("🌐 Starting OAuth2 flow for Gmail...")
                    
                    # Create OAuth flow from environment variables
                    client_config = {
                        "installed": {
                            "client_id": client_id,
                            "client_secret": client_secret,
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token",
                            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                            "redirect_uris": ["http://localhost"]
                        }
                    }
                    
                    flow = InstalledAppFlow.from_client_config(client_config, self.SCOPES)
                    creds = flow.run_local_server(port=0)
                    logger.info("✅ OAuth2 flow completed successfully")
                
                # Save credentials for next run
                os.makedirs(os.path.dirname(token_file), exist_ok=True)
                with open(token_file, 'w') as token:
                    token.write(creds.to_json())
                logger.info(f"💾 Gmail token saved to {token_file}")
            
            # Build Gmail service
            self.gmail_service = build('gmail', 'v1', credentials=creds)
            
            # Test the connection
            profile = self.gmail_service.users().getProfile(userId='me').execute()
            logger.info(f"✅ Gmail API authentication successful!")
            logger.info(f"   📧 Connected to: {profile.get('emailAddress')}")
            logger.info(f"   📊 Total messages: {profile.get('messagesTotal', 'Unknown')}")
            
        except Exception as e:
            logger.error(f"❌ Gmail authentication failed: {e}")
            raise
    
    async def _setup_gmail_labels(self):
        """Create Gmail labels for organization."""
        try:
            logger.info("🏷️ Setting up Gmail labels...")
            
            # Get existing labels
            existing_labels = self.gmail_service.users().labels().list(userId='me').execute()
            existing_label_names = [label['name'] for label in existing_labels.get('labels', [])]
            
            # Create missing labels
            created_labels = []
            for label_name in self.labels.values():
                if label_name not in existing_label_names:
                    label_object = {
                        'name': label_name,
                        'labelListVisibility': 'labelShow',
                        'messageListVisibility': 'show'
                    }
                    self.gmail_service.users().labels().create(
                        userId='me', 
                        body=label_object
                    ).execute()
                    created_labels.append(label_name)
                    logger.info(f"   ➕ Created Gmail label: {label_name}")
            
            if created_labels:
                logger.info(f"✅ Created {len(created_labels)} Gmail labels")
            else:
                logger.info("✅ All Gmail labels already exist")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup Gmail labels: {e}")
    
    def _is_business_hours(self) -> bool:
        """Check if current time is within business hours (8AM-6PM EST)."""
        try:
            import pytz
            est = pytz.timezone('US/Eastern')
            current_time = datetime.now(est)
            current_hour = current_time.hour
            
            is_business_time = self.business_hours['start'] <= current_hour < self.business_hours['end']
            
            if not is_business_time:
                logger.debug(f"⏰ Outside business hours: {current_time.strftime('%I:%M %p EST')} (Business: {self.business_hours['start']}AM-{self.business_hours['end']}PM)")
            
            return is_business_time
            
        except Exception as e:
            logger.warning(f"⚠️ Could not determine business hours: {e}")
            return True  # Default to processing if unsure
    
    def _should_process_email(self, email_data: Dict) -> Tuple[bool, str]:
        """Determine if an email should be processed based on filtering rules."""
        try:
            # Extract email metadata
            headers = {h['name']: h['value'] for h in email_data.get('payload', {}).get('headers', [])}
            sender = headers.get('From', '').lower()
            subject = headers.get('Subject', '').lower()
            
            logger.debug(f"📧 Evaluating email: From='{sender}', Subject='{subject[:50]}...'")
            
            # Check if email has attachments
            has_attachments = self._has_attachments(email_data)
            if not has_attachments:
                return False, "No attachments found"
            
            # Check approved senders
            sender_approved = any(pattern.lower() in sender for pattern in self.approved_senders)
            if not sender_approved:
                return False, f"Sender not in approved list: {sender}"
            
            # Check subject patterns
            subject_match = any(re.search(pattern, subject, re.IGNORECASE) for pattern in self.subject_patterns)
            if not subject_match:
                return False, f"Subject doesn't match patterns: {subject}"
            
            logger.info(f"✅ Email approved for processing: {sender}")
            return True, "Email approved for processing"
            
        except Exception as e:
            logger.error(f"❌ Error evaluating email: {e}")
            return False, f"Error evaluating email: {e}"
    
    def _has_attachments(self, email_data: Dict) -> bool:
        """Check if email has attachments."""
        try:
            def check_parts(parts):
                for part in parts:
                    if part.get('filename'):
                        return True
                    if 'parts' in part:
                        if check_parts(part['parts']):
                            return True
                return False
            
            payload = email_data.get('payload', {})
            if payload.get('filename'):
                return True
            
            if 'parts' in payload:
                return check_parts(payload['parts'])
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error checking attachments: {e}")
            return False
    
    async def scan_inbox(self) -> Dict[str, Any]:
        """Scan Gmail inbox for new emails to process."""
        try:
            # Check business hours
            if not self._is_business_hours():
                logger.info("Outside business hours, skipping email scan")
                return {
                    "status": "skipped",
                    "message": "Outside business hours",
                    "emails_processed": 0
                }
            
            logger.info("Starting Gmail inbox scan...")
            
            # Build search query for recent emails with attachments
            since_time = datetime.now() - timedelta(minutes=self.scan_interval_minutes + 5)  # 5 min buffer
            since_timestamp = int(since_time.timestamp())
            
            search_query = f"has:attachment after:{since_timestamp} -label:{self.labels['processed']}"
            
            # Search for emails
            search_result = self.gmail_service.users().messages().list(
                userId='me',
                q=search_query,
                maxResults=50  # Limit for safety
            ).execute()
            
            messages = search_result.get('messages', [])
            logger.info(f"Found {len(messages)} potential emails to process")
            
            # Process each email
            processed_count = 0
            for message in messages:
                try:
                    processed = await self._process_email(message['id'])
                    if processed:
                        processed_count += 1
                except Exception as e:
                    logger.error(f"Error processing email {message['id']}: {e}")
                    # Mark email with error label
                    await self._add_gmail_label(message['id'], self.labels['errors'])
            
            logger.info(f"Email scan completed. Processed {processed_count} emails")
            
            return {
                "status": "success",
                "emails_found": len(messages),
                "emails_processed": processed_count,
                "scan_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error scanning Gmail inbox: {e}")
            return {
                "status": "error",
                "message": str(e),
                "emails_processed": 0
            }
    
    async def _process_email(self, message_id: str) -> bool:
        """Process a single email and its attachments."""
        try:
            # Get full email data
            email_data = self.gmail_service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            # Check if email should be processed
            should_process, reason = self._should_process_email(email_data)
            if not should_process:
                logger.debug(f"Skipping email {message_id}: {reason}")
                return False
            
            logger.info(f"Processing email {message_id}: {reason}")
            
            # Extract email metadata
            headers = {h['name']: h['value'] for h in email_data.get('payload', {}).get('headers', [])}
            sender = headers.get('From', '')
            subject = headers.get('Subject', '')
            thread_id = email_data.get('threadId', '')
            
            # Extract email body
            email_body = await self._extract_email_body(email_data)
            
            # Extract and process attachments
            attachments = await self._extract_attachments(email_data, message_id)
            
            if not attachments:
                logger.warning(f"No valid attachments found in email {message_id}")
                return False
            
            # Check for duplicates
            duplicate_attachments = []
            new_attachments = []
            
            for attachment in attachments:
                attachment_hash = self._calculate_attachment_hash(attachment['content'])
                if attachment_hash in self.processed_attachments:
                    duplicate_attachments.append(attachment)
                else:
                    new_attachments.append(attachment)
                    self.processed_attachments[attachment_hash] = {
                        'first_seen': datetime.now().isoformat(),
                        'email_id': message_id,
                        'filename': attachment['filename']
                    }
            
            # Handle duplicates through HDL if any found
            if duplicate_attachments:
                await self._handle_duplicate_attachments(
                    message_id, sender, subject, duplicate_attachments, new_attachments
                )
            
            # Process new attachments
            if new_attachments:
                await self._process_email_attachments(
                    message_id, sender, subject, thread_id, email_body, new_attachments
                )
            
            # Mark email as processed
            await self._add_gmail_label(message_id, self.labels['processed'])
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing email {message_id}: {e}")
            return False
    
    async def _extract_email_body(self, email_data: Dict) -> str:
        """Extract email body text."""
        try:
            def extract_text_from_payload(payload):
                body_text = ""
                
                if payload.get('mimeType') == 'text/plain':
                    data = payload.get('body', {}).get('data')
                    if data:
                        body_text += base64.urlsafe_b64decode(data).decode('utf-8')
                
                elif payload.get('mimeType') == 'text/html':
                    data = payload.get('body', {}).get('data')
                    if data:
                        # Simple HTML to text conversion (you might want to use BeautifulSoup)
                        html_content = base64.urlsafe_b64decode(data).decode('utf-8')
                        import re
                        text_content = re.sub(r'<[^>]+>', '', html_content)
                        body_text += text_content
                
                elif 'parts' in payload:
                    for part in payload['parts']:
                        body_text += extract_text_from_payload(part)
                
                return body_text
            
            return extract_text_from_payload(email_data.get('payload', {}))
            
        except Exception as e:
            logger.error(f"Error extracting email body: {e}")
            return ""
    
    async def _extract_attachments(self, email_data: Dict, message_id: str) -> List[Dict]:
        """Extract attachments from email."""
        attachments = []
        
        try:
            def extract_from_parts(parts):
                for part in parts:
                    if part.get('filename') and part.get('body', {}).get('attachmentId'):
                        # Download attachment
                        attachment_id = part['body']['attachmentId']
                        attachment_data = self.gmail_service.users().messages().attachments().get(
                            userId='me',
                            messageId=message_id,
                            id=attachment_id
                        ).execute()
                        
                        file_data = base64.urlsafe_b64decode(attachment_data['data'])
                        
                        attachments.append({
                            'filename': part['filename'],
                            'mime_type': part.get('mimeType', 'application/octet-stream'),
                            'content': file_data,
                            'size': len(file_data)
                        })
                    
                    elif 'parts' in part:
                        extract_from_parts(part['parts'])
            
            payload = email_data.get('payload', {})
            if 'parts' in payload:
                extract_from_parts(payload['parts'])
            
            logger.info(f"Extracted {len(attachments)} attachments from email {message_id}")
            return attachments
            
        except Exception as e:
            logger.error(f"Error extracting attachments: {e}")
            return []
    
    def _calculate_attachment_hash(self, content: bytes) -> str:
        """Calculate hash for duplicate detection."""
        return hashlib.sha256(content).hexdigest()
    
    async def _handle_duplicate_attachments(self, message_id: str, sender: str, subject: str, 
                                         duplicates: List[Dict], new_attachments: List[Dict]):
        """Handle duplicate attachments through HDL workflow."""
        try:
            # Mark email with duplicate label
            await self._add_gmail_label(message_id, self.labels['duplicates'])
            
            # Prepare HDL request for duplicates
            duplicate_info = {
                "email_id": message_id,
                "sender": sender,
                "subject": subject,
                "duplicate_files": [att['filename'] for att in duplicates],
                "new_files": [att['filename'] for att in new_attachments] if new_attachments else [],
                "action_needed": "duplicate_decision"
            }
            
            # Send to HDL Agent via Agent Coordinator
            if self.agent_coordinator:
                hdl_response = await self.agent_coordinator.route_message(
                    source="EMAIL_SCANNER",
                    target="HDL_AGENT",
                    message={
                        "action": "review_duplicate_attachments",
                        "data": duplicate_info
                    }
                )
                logger.info(f"Duplicate attachments sent to HDL: {hdl_response}")
            
        except Exception as e:
            logger.error(f"Error handling duplicate attachments: {e}")
    
    async def _process_email_attachments(self, message_id: str, sender: str, subject: str,
                                       thread_id: str, email_body: str, attachments: List[Dict]):
        """Process email attachments through the document pipeline."""
        try:
            for attachment in attachments:
                # Save attachment temporarily
                with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{attachment['filename']}") as temp_file:
                    temp_file.write(attachment['content'])
                    temp_file_path = temp_file.name
                
                try:
                    # Process through extraction agent
                    if self.agent_coordinator:
                        document_data = {
                            "file_name": attachment['filename'],
                            "content": attachment['content'].decode('utf-8', errors='ignore'),
                            "file_metadata": {
                                "source": "email",
                                "email_id": message_id,
                                "thread_id": thread_id,
                                "sender": sender,
                                "subject": subject,
                                "received_date": datetime.now().isoformat(),
                                "attachment_info": {
                                    "mime_type": attachment['mime_type'],
                                    "size": attachment['size']
                                }
                            }
                        }
                        
                        extraction_response = await self.agent_coordinator.route_message(
                            source="EMAIL_SCANNER",
                            target="EXTRACTION_AGENT",
                            message={
                                "action": "extract_document",
                                "data": document_data
                            }
                        )
                        
                        # Store email context in Vector DB
                        if self.vector_service:
                            email_context = f"""
                            Email Subject: {subject}
                            From: {sender}
                            Email Body: {email_body}
                            Attachment: {attachment['filename']}
                            """
                            
                            await self.vector_service.store_document(
                                content=email_context,
                                metadata={
                                    "source": "email",
                                    "email_id": message_id,
                                    "thread_id": thread_id,
                                    "sender": sender,
                                    "subject": subject,
                                    "attachment_name": attachment['filename']
                                }
                            )
                        
                        logger.info(f"Processed attachment {attachment['filename']} from email {message_id}")
                
                finally:
                    # Clean up temp file
                    if os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)
            
        except Exception as e:
            logger.error(f"Error processing email attachments: {e}")
    
    async def _add_gmail_label(self, message_id: str, label_name: str):
        """Add Gmail label to message."""
        try:
            # Get label ID
            labels_result = self.gmail_service.users().labels().list(userId='me').execute()
            label_id = None
            for label in labels_result.get('labels', []):
                if label['name'] == label_name:
                    label_id = label['id']
                    break
            
            if label_id:
                self.gmail_service.users().messages().modify(
                    userId='me',
                    id=message_id,
                    body={'addLabelIds': [label_id]}
                ).execute()
            
        except Exception as e:
            logger.error(f"Error adding Gmail label: {e}")

    async def get_email_thread_context(self, thread_id: str) -> Dict[str, Any]:
        """Get full email thread context for entity linking."""
        try:
            thread_data = self.gmail_service.users().threads().get(
                userId='me',
                id=thread_id
            ).execute()
            
            messages = []
            for message in thread_data.get('messages', []):
                headers = {h['name']: h['value'] for h in message.get('payload', {}).get('headers', [])}
                messages.append({
                    'id': message['id'],
                    'sender': headers.get('From', ''),
                    'subject': headers.get('Subject', ''),
                    'date': headers.get('Date', ''),
                    'body': await self._extract_email_body(message)
                })
            
            return {
                "thread_id": thread_id,
                "messages": messages,
                "message_count": len(messages)
            }
            
        except Exception as e:
            logger.error(f"Error getting email thread context: {e}")
            return {}
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get comprehensive service status."""
        return {
            "service": "EmailScanningService",
            "initialized": self.gmail_service is not None,
            "scan_interval": f"{self.scan_interval_minutes} minutes",
            "business_hours": f"{self.business_hours['start']}AM - {self.business_hours['end']}PM EST",
            "current_time_est": datetime.now().strftime('%I:%M %p EST'),
            "business_hours_active": self._is_business_hours(),
            "approved_senders": self.approved_senders,
            "subject_patterns": self.subject_patterns,
            "labels": self.labels,
            "processed_attachments_count": len(self.processed_attachments)
        }
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test Gmail API connection and return status."""
        try:
            if not self.gmail_service:
                return {
                    "status": "error",
                    "message": "Gmail service not initialized"
                }
            
            # Get profile information
            profile = self.gmail_service.users().getProfile(userId='me').execute()
            
            # Get recent message count
            recent_messages = self.gmail_service.users().messages().list(
                userId='me',
                maxResults=5,
                q="has:attachment"
            ).execute()
            
            return {
                "status": "success",
                "gmail_connected": True,
                "email_address": profile.get('emailAddress'),
                "total_messages": profile.get('messagesTotal'),
                "recent_messages_with_attachments": len(recent_messages.get('messages', [])),
                "business_hours_active": self._is_business_hours(),
                "approved_senders": len(self.approved_senders),
                "subject_patterns": len(self.subject_patterns),
                "labels_configured": list(self.labels.values())
            }
            
        except Exception as e:
            logger.error(f"❌ Gmail connection test failed: {e}")
            return {
                "status": "error",
                "message": str(e),
                "gmail_connected": False
            }
    
    async def scan_inbox_preview(self, max_results: int = 10) -> Dict[str, Any]:
        """Preview emails that would be processed (for testing)."""
        try:
            if not self.gmail_service:
                return {"status": "error", "message": "Gmail service not initialized"}
            
            logger.info(f"🔍 Scanning inbox for emails with attachments (preview mode)...")
            
            # Search for recent emails with attachments
            search_query = "has:attachment -label:Gabriel/Processed"
            
            search_result = self.gmail_service.users().messages().list(
                userId='me',
                q=search_query,
                maxResults=max_results
            ).execute()
            
            messages = search_result.get('messages', [])
            logger.info(f"📧 Found {len(messages)} emails with attachments")
            
            # Analyze each email
            email_analysis = []
            for message in messages:
                try:
                    email_data = self.gmail_service.users().messages().get(
                        userId='me',
                        id=message['id'],
                        format='full'
                    ).execute()
                    
                    headers = {h['name']: h['value'] for h in email_data.get('payload', {}).get('headers', [])}
                    should_process, reason = self._should_process_email(email_data)
                    
                    email_analysis.append({
                        "id": message['id'],
                        "sender": headers.get('From', 'Unknown'),
                        "subject": headers.get('Subject', 'No Subject'),
                        "date": headers.get('Date', 'Unknown'),
                        "should_process": should_process,
                        "reason": reason,
                        "has_attachments": self._has_attachments(email_data)
                    })
                    
                except Exception as e:
                    email_analysis.append({
                        "id": message['id'],
                        "error": str(e)
                    })
            
            processable_count = sum(1 for email in email_analysis if email.get('should_process', False))
            
            return {
                "status": "success",
                "total_emails_found": len(messages),
                "emails_processable": processable_count,
                "business_hours_active": self._is_business_hours(),
                "email_analysis": email_analysis
            }
            
        except Exception as e:
            logger.error(f"❌ Error previewing inbox: {e}")
            return {
                "status": "error",
                "message": str(e)
            } 