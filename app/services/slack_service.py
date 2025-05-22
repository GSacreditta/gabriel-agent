import logging
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class SlackService:
    """Service for handling Slack integration."""
    
    def __init__(self):
        """Initialize the Slack service with credentials from settings."""
        self.client = WebClient(token=settings.SLACK_BOT_TOKEN)
        self.default_channel = settings.SLACK_DEFAULT_CHANNEL
        
    async def send_message(self, message: str, channel: str = None) -> dict:
        """Send a message to a Slack channel.
        
        Args:
            message (str): The message to send
            channel (str, optional): The channel to send to. Defaults to default_channel.
            
        Returns:
            dict: Response from Slack API
        """
        try:
            channel = channel or self.default_channel
            response = self.client.chat_postMessage(
                channel=channel,
                text=message
            )
            return {"success": True, "response": response}
        except SlackApiError as e:
            logger.error(f"Error sending message to Slack: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def send_review_request(self, message: str, channel: str = None) -> dict:
        """Send a message that requires review, with reaction options.
        
        Args:
            message (str): The message to send
            channel (str, optional): The channel to send to. Defaults to default_channel.
            
        Returns:
            dict: Response from Slack API
        """
        try:
            channel = channel or self.default_channel
            # Add review instructions to the message
            review_message = f"{message}\n\n*Please review this response:*\n:white_check_mark: Approve\n:x: Reject"
            
            response = self.client.chat_postMessage(
                channel=channel,
                text=review_message
            )
            return {"success": True, "response": response}
        except SlackApiError as e:
            logger.error(f"Error sending review request to Slack: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def get_channel_messages(self, channel: str, limit: int = 100) -> dict:
        """Get recent messages from a channel.
        
        Args:
            channel (str): The channel to get messages from
            limit (int, optional): Maximum number of messages to retrieve. Defaults to 100.
            
        Returns:
            dict: Response containing messages
        """
        try:
            response = self.client.conversations_history(
                channel=channel,
                limit=limit
            )
            return {"success": True, "messages": response["messages"]}
        except SlackApiError as e:
            logger.error(f"Error getting channel messages: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def get_reactions(self, channel: str, timestamp: str) -> dict:
        """Get reactions for a specific message.
        
        Args:
            channel (str): The channel containing the message
            timestamp (str): The timestamp of the message
            
        Returns:
            dict: Response containing reactions
        """
        try:
            response = self.client.reactions_get(
                channel=channel,
                timestamp=timestamp
            )
            return {"success": True, "reactions": response.get("message", {}).get("reactions", [])}
        except SlackApiError as e:
            logger.error(f"Error getting reactions: {str(e)}")
            return {"success": False, "error": str(e)} 