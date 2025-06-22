"""Mock Slack service for testing."""

import logging
from slack_sdk import WebClient
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.errors import SlackApiError
from app.core.config import get_settings
from app.services.handler_vector import HandlerVector
import traceback
from typing import Dict, Any, Optional
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)
settings = get_settings()

class SlackService:
    """Simple Slack service mock for testing."""

    async def send_message(
        self,
        text: str,
        blocks: list = None,
        channel: str = None
    ) -> Dict[str, Any]:
        """Send a message to Slack."""
        try:
            channel = channel or self.default_channel
            response = self.client.chat_postMessage(
                channel=channel,
                text=text,
                blocks=blocks
            )
            return {
                "success": True,
                "message_ts": response["ts"],
                "channel": response["channel"]
            }
        except SlackApiError as e:
            logger.error(f"Failed to send Slack message: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def update_message(
        self,
        message_ts: str,
        text: str,
        channel: str = None
    ) -> Dict[str, Any]:
        """Mock updating a Slack message."""
        logger.info(f"Mock update message {message_ts}: {text}")
        return {
            "success": True,
            "message_ts": message_ts
        }

    def __init__(self):
        """Initialize the Slack service with credentials from settings."""
        try:
            if not settings.SLACK_BOT_TOKEN:
                raise ValueError("SLACK_BOT_TOKEN not set")
            
            self.client = WebClient(token=settings.SLACK_BOT_TOKEN)
            self.socket_client = None
            self.default_channel = settings.SLACK_DEFAULT_CHANNEL
            self.is_running = False
            self.socket_task = None
            self.agent = None  # Will be set during initialization
            self.handler_vector = None  # Will be set during initialization
            logger.info("SlackService instance created")
        except Exception as e:
            logger.error(f"Failed to create SlackService instance: {str(e)}")
            raise
    
    async def initialize(self, agent, document_processor=None, drive_service=None, vector_service=None):
        """Initialize the service with required dependencies."""
        try:
            logger.info("Initializing SlackService with agent and handlers...")
            self.agent = agent
            
            # Initialize HandlerVector if we have all required services
            if document_processor and drive_service and vector_service:
                self.handler_vector = HandlerVector(
                    document_processor=document_processor,
                    drive_service=drive_service,
                    vector_service=vector_service,
                    slack_service=self
                )
                logger.info("HandlerVector initialized successfully")
            else:
                logger.warning("Missing services for HandlerVector initialization")
            
            # Test Slack connection synchronously
            try:
                auth_test = self.client.auth_test()
                if not auth_test["ok"]:
                    logger.error(f"Slack auth test failed: {auth_test.get('error', 'Unknown error')}")
                    return False
                logger.info(f"Connected to Slack as {auth_test['user_id']} in team {auth_test['team']}")
            except Exception as e:
                logger.error(f"Failed to authenticate with Slack: {str(e)}")
                return False
            
            # Start socket mode if configured
            if settings.SLACK_APP_TOKEN:
                socket_success = await self.start_socket_mode()
                if not socket_success:
                    logger.warning("Failed to start Socket Mode, continuing in HTTP-only mode")
            else:
                logger.warning("SLACK_APP_TOKEN not set, running in HTTP-only mode")
            
            logger.info("SlackService initialization complete")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize SlackService: {str(e)}")
            logger.error(f"Traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")
            return False
    
    async def start_socket_mode(self):
        """Start the Socket Mode client."""
        try:
            if not settings.SLACK_APP_TOKEN:
                logger.warning("Slack App Token not set, skipping Socket Mode")
                return True
            
            if self.is_running:
                logger.warning("Socket Mode already running")
                return True
            
            logger.info("Starting Slack Socket Mode...")
            self.socket_client = SocketModeClient(
                app_token=settings.SLACK_APP_TOKEN,
                web_client=self.client
            )
            
            # Set up socket mode handlers
            self.socket_client.socket_mode_request_listeners.append(self._handle_socket_request)
            
            # Start socket mode client
            self.socket_client.connect()
            self.is_running = True
            logger.info("Slack Socket Mode started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error starting Socket Mode: {str(e)}")
            logger.error(f"Traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")
            return False
    
    async def stop_socket_mode(self):
        """Stop the Socket Mode client."""
        try:
            if not self.is_running:
                return
            
            logger.info("Stopping Slack Socket Mode...")
            if self.socket_client:
                self.socket_client.disconnect()
                self.socket_client = None
            
            self.is_running = False
            logger.info("Slack Socket Mode stopped")
            
        except Exception as e:
            logger.error(f"Error stopping Socket Mode: {str(e)}")
    
    async def cleanup(self):
        """Cleanup Slack resources."""
        try:
            await self.stop_socket_mode()
            logger.info("Slack resources cleaned up")
        except Exception as e:
            logger.warning(f"Error during Slack cleanup: {str(e)}")
    
    def _handle_socket_request(self, client: SocketModeClient, req: SocketModeRequest):
        """Handle incoming Socket Mode requests."""
        try:
            # Acknowledge the request
            response = SocketModeResponse(envelope_id=req.envelope_id)
            client.send_socket_mode_response(response)
            
            # Process the event
            if req.type == "events_api":
                event = req.payload["event"]
                # Create a new event loop for this thread if needed
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                # Run the async handler in the event loop
                if event.get("type") == "message":
                    logger.debug(f"[DEBUG] Creating task to handle message: {event}")
                    loop.create_task(self._handle_message(event))
                else:
                    self._handle_event(event)
            elif req.type == "interactive":
                self._handle_interactive(req.payload)
            elif req.type == "slash_commands":
                self._handle_command(req.payload)
                
        except Exception as e:
            logger.error(f"Error handling socket request: {str(e)}")
            logger.error(f"Traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")
    
    def _handle_event(self, event: dict):
        """Handle Slack events."""
        try:
            event_type = event.get("type")
            if event_type == "message":
                self._handle_message(event)
            
        except Exception as e:
            logger.error(f"Error handling event: {str(e)}")
    
    async def _parse_human_response(self, text: str) -> Dict[str, Any]:
        """Parse human response to document review request."""
        text = text.lower().strip()
        
        # Initialize response object
        response = {
            "action": None,
            "entity_name": None,
            "corrections": {}
        }
        
        # Check for approval keywords
        if any(word in text for word in ["approve", "approved", "accept", "accepted", "yes", "👍", "✅"]):
            response["action"] = "approve"
            # Try to extract entity name if provided with approval
            if "as" in text:
                entity = text.split("as")[-1].strip()
                response["entity_name"] = entity
            
        # Check for correction keywords
        elif any(word in text for word in ["correct", "fix", "change", "update"]):
            response["action"] = "correct"
            # Extract corrections (e.g., "correct entity to Apple Inc")
            if "entity to" in text:
                entity = text.split("entity to")[-1].strip()
                response["entity_name"] = entity
                response["corrections"]["entity_name"] = entity
        
        return response

    async def wait_for_response(self, channel: str, thread_ts: str, timeout: int = 300) -> Optional[Dict[str, Any]]:
        """Wait for a human response in a specific thread.
        
        Args:
            channel: Channel ID where the message was sent
            thread_ts: Thread timestamp to monitor
            timeout: How long to wait for response in seconds
            
        Returns:
            Dict containing the parsed response or None if no valid response received
        """
        start_time = datetime.now()
        
        while (datetime.now() - start_time).total_seconds() < timeout:
            try:
                # Get replies in thread
                result = await self.client.conversations_replies(
                    channel=channel,
                    ts=thread_ts
                )
                
                if result["ok"] and result["messages"]:
                    # Look for human responses (non-bot messages)
                    for message in result["messages"]:
                        if not message.get("bot_id") and message.get("ts") != thread_ts:
                            # Found a human response, parse it
                            response = await self._parse_human_response(message["text"])
                            if response["action"]:
                                return response
                
                # Wait before checking again
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error checking for responses: {str(e)}")
                await asyncio.sleep(5)
                
        logger.warning(f"Timeout waiting for response after {timeout} seconds")
        return None

    async def _handle_message(self, event: dict):
        """Handle message events."""
        try:
            channel = event.get("channel")
            text = event.get("text", "").strip()
            user = event.get("user")
            subtype = event.get("subtype")
            channel_type = event.get("channel_type", "")
            thread_ts = event.get("thread_ts")  # Get thread timestamp if it exists
            
            logger.debug(f"[DEBUG] Message event received: {event}")
            logger.info(f"Received message - Channel: {channel}, User: {user}, Text: {text}, Type: {channel_type}")
            
            if not text or not channel or not user:
                logger.debug("[DEBUG] Missing required fields in message")
                return

            # Ignore messages from bots (including ourselves)
            if event.get("bot_id") or subtype == "bot_message":
                logger.debug(f"Ignoring bot message from {user}")
                return

            # Check if this is a reply to our review request
            if thread_ts:
                # Get the parent message
                parent_message = await self.get_message(channel, thread_ts)
                if parent_message and parent_message.get("bot_id"):  # If parent was from our bot
                    # Parse the response
                    response = await self._parse_human_response(text)
                    
                    if response["action"] in ["approve", "correct"]:
                        # Extract file_id from the parent message
                        parent_text = parent_message.get("text", "")
                        file_id = None
                        if "Drive Link:" in parent_text:
                            file_id = parent_text.split("Drive Link:")[-1].split("/")[-1].strip()
                        
                        if file_id:
                            # Call HandlerVector to process the approval/correction
                            try:
                                result = await self.handler_vector.handle_approval(
                                    file_id=file_id,
                                    approved_entity=response["entity_name"],
                                    human_corrections=response.get("corrections")
                                )
                                
                                if not result["success"]:
                                    await self.send_message(
                                        f"❌ Failed to process approval: {result.get('error', 'Unknown error')}",
                                        channel=channel,
                                        thread_ts=thread_ts
                                    )
                            except Exception as e:
                                logger.error(f"Error processing approval: {str(e)}")
                                await self.send_message(
                                    f"❌ Error processing approval: {str(e)}",
                                    channel=channel,
                                    thread_ts=thread_ts
                                )
                        else:
                            await self.send_message(
                                "❌ Could not find file ID in the original message",
                                channel=channel,
                                thread_ts=thread_ts
                            )
                    return

            # Handle other messages (non-approval related)
            bot_user_id = self.client.auth_test()["user_id"]
            is_mentioned = f"<@{bot_user_id}>" in text
            
            # Respond to:
            # 1. Direct mentions in any channel
            # 2. Direct messages (DM/IM channels)
            # 3. Messages in channels that start with the bot's name
            should_respond = (
                is_mentioned or 
                channel_type in ["im", "mpim"] or
                text.lower().startswith(("gabriel", "hey gabriel", "hi gabriel"))
            )
            
            if not should_respond:
                logger.debug(f"Ignoring message - not mentioned and not a DM. Channel type: {channel_type}")
                return

            logger.info(f"Processing message from user {user}: {text}")

            # Remove the bot mention from the text if present
            if is_mentioned:
                mention = f"<@{bot_user_id}>"
                text = text.replace(mention, "").strip()
                logger.debug(f"Removed bot mention. New text: {text}")

            if not self.agent:
                logger.error("Agent not initialized")
                await self.send_message(
                    "Sorry, I'm not fully initialized yet. Please try again in a moment.",
                    channel=channel
                )
                return

            # Process the message with the agent
            try:
                response = await self.agent.process_message(text)
                if response:
                    await self.send_message(response, channel=channel)
            except Exception as e:
                logger.error(f"Error processing message with agent: {str(e)}")
                await self.send_message(
                    f"Sorry, I encountered an error while processing your message: {str(e)}",
                    channel=channel
                )
                
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")

    async def get_message(self, channel: str, message_ts: str) -> Optional[Dict[str, Any]]:
        """Get a specific message from a channel."""
        try:
            result = self.client.conversations_history(
                channel=channel,
                latest=message_ts,
                limit=1,
                inclusive=True
            )
            
            if result["ok"] and result["messages"]:
                return result["messages"][0]
            return None
        except Exception as e:
            logger.error(f"Error getting message: {str(e)}")
            return None
    
    def _handle_interactive(self, payload: dict):
        """Handle interactive component actions."""
        try:
            # Process interactive components synchronously
            pass
        except Exception as e:
            logger.error(f"Error handling interactive: {str(e)}")
    
    def _handle_command(self, payload: dict):
        """Handle slash commands."""
        try:
            # Process slash commands synchronously
            pass
        except Exception as e:
            logger.error(f"Error handling command: {str(e)}")
    
    async def send_review_request(self, message: str, channel: str = None) -> dict:
        """Send a document review request to Slack.
        
        Args:
            message (str): The message to send
            channel (str, optional): Channel to send to. Defaults to default_channel.
            
        Returns:
            dict: Response from Slack API
        """
        try:
            target_channel = channel or self.default_channel
            if not target_channel:
                raise ValueError("No target channel specified")
            
            response = await self.client.chat_postMessage(
                channel=target_channel,
                text=message,
                mrkdwn=True
            )
            
            if not response["ok"]:
                raise SlackApiError("Failed to send message", response)
                
            logger.info(f"Successfully sent review request to channel {target_channel}")
            return response
            
        except Exception as e:
            logger.error(f"Error sending review request: {str(e)}")
            raise
            
    def get_channel_messages(self, channel: str, limit: int = 100) -> dict:
        """Get recent messages from a channel."""
        try:
            response = self.client.conversations_history(
                channel=channel,
                limit=limit
            )
            return {"success": True, "messages": response["messages"]}
        except SlackApiError as e:
            logger.error(f"Error getting channel messages: {str(e)}")
            return {"success": False, "error": str(e)}
            
    def get_reactions(self, channel: str, timestamp: str) -> dict:
        """Get reactions for a specific message."""
        try:
            response = self.client.reactions_get(
                channel=channel,
                timestamp=timestamp
            )
            return {"success": True, "reactions": response.get("message", {}).get("reactions", [])}
        except SlackApiError as e:
            logger.error(f"Error getting reactions: {str(e)}")
            return {"success": False, "error": str(e)} 