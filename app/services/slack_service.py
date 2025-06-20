import logging
from slack_sdk import WebClient
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.errors import SlackApiError
from app.core.config import get_settings
import traceback

logger = logging.getLogger(__name__)
settings = get_settings()

class SlackService:
    """Service for handling Slack integration."""
    
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
            logger.info("SlackService instance created")
        except Exception as e:
            logger.error(f"Failed to create SlackService instance: {str(e)}")
            raise
    
    async def initialize(self, agent):
        """Initialize the service with required dependencies."""
        try:
            logger.info("Initializing SlackService with agent...")
            self.agent = agent
            
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
                self._handle_event(event)
            elif req.type == "interactive":
                self._handle_interactive(req.payload)
            elif req.type == "slash_commands":
                self._handle_command(req.payload)
                
        except Exception as e:
            logger.error(f"Error handling socket request: {str(e)}")
    
    def _handle_event(self, event: dict):
        """Handle Slack events."""
        try:
            event_type = event.get("type")
            if event_type == "message":
                self._handle_message(event)
            
        except Exception as e:
            logger.error(f"Error handling event: {str(e)}")
    
    def _handle_message(self, event: dict):
        """Handle message events."""
        try:
            channel = event.get("channel")
            text = event.get("text", "").strip()
            user = event.get("user")
            subtype = event.get("subtype")
            channel_type = event.get("channel_type", "")
            
            logger.info(f"Received message - Channel: {channel}, User: {user}, Text: {text}, Type: {channel_type}")
            
            if not text or not channel or not user:
                return

            # Ignore messages from bots (including ourselves)
            if event.get("bot_id") or subtype == "bot_message":
                logger.debug(f"Ignoring bot message from {user}")
                return

            # Check if the message mentions our bot
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
                # Handle both formats: <@U123> and <@U123ABC>
                mention = f"<@{bot_user_id}>"
                text = text.replace(mention, "").strip()
                logger.debug(f"Removed bot mention. New text: {text}")

            if not self.agent:
                logger.error("Agent not initialized")
                self.client.chat_postMessage(
                    channel=channel,
                    text="I'm not fully initialized yet. Please try again in a moment."
                )
                return

            try:
                # Process message synchronously since we're in a socket callback
                logger.debug(f"Sending message to agent for processing: {text}")
                response = self.agent.process_message_sync(text)
                logger.debug(f"Received response from agent: {response}")
                
                if response:
                    self.client.chat_postMessage(
                        channel=channel,
                        text=response
                    )
                    logger.info(f"Sent response to channel {channel}")
                else:
                    logger.warning("Agent returned empty response")
                    self.client.chat_postMessage(
                        channel=channel,
                        text="I'm sorry, I couldn't process that request."
                    )
            except Exception as e:
                logger.error(f"Error getting response from agent: {str(e)}")
                logger.error(f"Traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")
                self.client.chat_postMessage(
                    channel=channel,
                    text="I encountered an error while processing your request. Please try again."
                )
            
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            logger.error(f"Traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")
            try:
                self.client.chat_postMessage(
                    channel=channel,
                    text="An error occurred while processing your message."
                )
            except Exception as send_error:
                logger.error(f"Failed to send error message: {str(send_error)}")
    
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
    
    def send_message(self, message: str, channel: str = None) -> dict:
        """Send a message to a Slack channel."""
        try:
            if not self.client:
                logger.error("Slack client not initialized")
                return {"success": False, "error": "Slack client not initialized"}
            
            channel = channel or self.default_channel
            logger.info(f"Sending message to channel {channel}: {message}")
            
            response = self.client.chat_postMessage(
                channel=channel,
                text=message
            )
            
            if not response["ok"]:
                logger.error(f"Failed to send message: {response.get('error', 'Unknown error')}")
                return {"success": False, "error": response.get("error")}
            
            logger.debug(f"Message sent successfully: {response}")
            return {"success": True, "response": response}
            
        except SlackApiError as e:
            logger.error(f"Slack API error: {str(e)}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Error sending message to Slack: {str(e)}")
            return {"success": False, "error": str(e)}
            
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