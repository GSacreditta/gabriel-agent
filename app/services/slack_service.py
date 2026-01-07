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
        channel: str = None,
        thread_ts: str = None
    ) -> Dict[str, Any]:
        """Send a message to Slack."""
        try:
            channel = channel or self.default_channel
            # Build the message payload
            message_payload = {
                "channel": channel,
                "text": text
            }
            
            # Add optional parameters if provided
            if blocks:
                message_payload["blocks"] = blocks
            if thread_ts:
                message_payload["thread_ts"] = thread_ts
                
            response = self.client.chat_postMessage(**message_payload)
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
            
            # Get bot user ID to prevent processing our own messages
            try:
                auth_response = self.client.auth_test()
                self.bot_user_id = auth_response["user_id"]
                logger.info(f"Bot user ID: {self.bot_user_id}")
            except Exception as e:
                logger.warning(f"Could not get bot user ID: {e}")
                self.bot_user_id = None
                
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
        """Parse human response to document review request using natural language understanding."""
        import re
        
        original_text = text.strip()
        text_lower = text.lower().strip()
        
        # Initialize response object - more flexible structure
        response = {
            "action": None,
            "corrections": {},
            "feedback": original_text  # Always preserve original user feedback
        }
        
        # 🔥 REJECTION PATTERNS - More conversational
        rejection_patterns = [
            r'\b(no|nope|reject|rejected|deny|denied|cancel|wrong|incorrect|not correct|not right|❌|👎)\b',
            r'\b(don\'t approve|do not approve|don\'t accept|do not accept)\b',
            r'\b(that\'s wrong|this is wrong|not good|not ok)\b'
        ]
        
        for pattern in rejection_patterns:
            if re.search(pattern, text_lower):
                response["action"] = "reject"
                return response
        
        # 🔥 GENERIC VALUE EXTRACTION - Handle any type of correction
        # Look for patterns like "change X to Y", "set X as Y", "X should be Y"
        value_patterns = [
            # Bracketed format: [Any Value]
            r'\[([^\]]+)\]',
            # Quoted format: "Any Value"
            r'"([^"]+)"',
            r"'([^']+)'",
            # "yes but call it X", "ok but make it X"
            r'\b(?:yes|ok|okay)\s+but\s+(?:call|make|set)\s+it\s+(.+?)(?:\.|$)',
            # "approve as X", "accept as X" 
            r'\b(?:approve|accept)\s+(?:it\s+)?as\s+(.+?)(?:\.|$)',
            # "change it to X", "correct it to X", "fix it to X" - more generic
            r'\b(?:change|correct|fix|update|modify)\s+(?:it|this|that|the\s+\w+)?\s*(?:to|as)\s+(.+?)(?:\.|$)',
            # "it should be X", "the [field] should be X" - more generic
            r'\b(?:it|this|that|the\s+\w+)\s+(?:should|must)\s+be\s+(.+?)(?:\.|$)',
            # "make it X", "set it to X" - more generic
            r'\b(?:make|set)\s+(?:it|this|that|the\s+\w+)?\s*(?:to|as)?\s+(.+?)(?:\.|$)',
            # "[field] is X", "value is X", "amount is X" - more generic
            r'\b(?:\w+)\s+(?:is|should\s+be)\s+(.+?)(?:\.|$)',
            # "call it X", "name it X"
            r'\b(?:call|name)\s+it\s+(.+?)(?:\.|$)',
            # Just the value after common words
            r'\b(?:to|as)\s+(.+?)(?:\.|$)'
        ]
        
        extracted_values = []
        for pattern in value_patterns:
            matches = re.finditer(pattern, original_text, re.IGNORECASE)
            for match in matches:
                value = match.group(1).strip()
                # Clean up common artifacts
                value = re.sub(r'^["\'\[\]]+|["\'\[\]]+$', '', value)
                value = value.strip()
                if value and len(value) > 1:
                    extracted_values.append(value)
        
        # 🔥 CORRECTION PATTERNS - More flexible
        correction_indicators = [
            r'\b(change|correct|fix|update|modify|adjust|alter)\b',
            r'\b(it should be|should be|make it|set it to)\b',
            r'\b(instead of|rather than|not)\b.*\b(it should be|should be)\b'
        ]
        
        is_correction = any(re.search(pattern, text_lower) for pattern in correction_indicators)
        
        if is_correction:
            response["action"] = "correct"
            # Store all extracted values - let the downstream system decide what to do with them
            if extracted_values:
                response["corrections"]["suggested_values"] = extracted_values
                response["corrections"]["primary_value"] = extracted_values[0]
            return response
        
        # 🔥 APPROVAL PATTERNS - More conversational
        approval_patterns = [
            r'\b(yes|yep|ok|okay|good|fine|right|approve|approved|accept|accepted|✅|👍)\b',
            r'\b(looks good|looks fine|looks correct|looks right|that\'s right|that\'s correct)\b',
            r'\b(go ahead|proceed|continue|confirm|confirmed)\b',
            r'\b(approve it|accept it|good to go|all good|perfect)\b'
        ]
        
        # Special handling for "that's correct" - should be approval, not correction
        if re.search(r'\b(that\'s|thats)\s+(correct|right|good)\b', text_lower):
            response["action"] = "approve"
            if extracted_values:
                response["corrections"]["suggested_values"] = extracted_values
                response["corrections"]["primary_value"] = extracted_values[0]
            return response
        
        is_approval = any(re.search(pattern, text_lower) for pattern in approval_patterns)
        
        if is_approval:
            response["action"] = "approve"
            # If values were mentioned with approval, include them
            if extracted_values:
                response["corrections"]["suggested_values"] = extracted_values
                response["corrections"]["primary_value"] = extracted_values[0]
            return response
        
        # 🔥 FALLBACK - If we found values but no clear action, assume correction
        if extracted_values:
            response["action"] = "correct"
            response["corrections"]["suggested_values"] = extracted_values
            response["corrections"]["primary_value"] = extracted_values[0]
        
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
            # Fixed: Also check bot_profile and our own user_id to prevent message loops
            if (event.get("bot_id") or 
                subtype == "bot_message" or 
                event.get("bot_profile") or
                user == self.bot_user_id):
                logger.debug(f"Ignoring bot message from {user}")
                return

            # Check if this is a reply to our review request
            if thread_ts:
                logger.info(f"🧵 Thread reply detected - thread_ts: {thread_ts}")
                # Get the parent message
                
                parent_message = await self.get_message(channel, thread_ts)
                logger.info(f"📄 Parent message retrieved: {parent_message is not None}")
                if parent_message:
                    logger.info(f"🤖 Parent has bot_id: {parent_message.get('bot_id') is not None}")
                    logger.info(f"📝 Parent text preview: {parent_message.get('text', '')[:100]}...")
                
                if parent_message and parent_message.get("bot_id"):  # If parent was from our bot
                    # Parse the response
                    response = await self._parse_human_response(text)
                    
                    if response["action"] in ["approve", "correct", "reject"]:
                        parent_text = parent_message.get("text", "")
                        
                        # 🔥 NEW: Check if this is an HDL Agent review request
                        logger.info(f"🔍 Checking parent text for 'Request ID:' - found: {'Request ID:' in parent_text}")
                        if "Request ID:" in parent_text:
                            # Extract request_id from HDL Agent message
                            try:
                                request_id = None
                                for line in parent_text.split('\n'):
                                    if "Request ID:" in line:
                                        request_id = line.split('`')[1] if '`' in line else line.split(':')[1].strip()
                                        break
                                
                                if request_id:
                                    logger.info(f"Processing HDL Agent response: {response['action']} for request {request_id}")
                                    
                                    # Send initial acknowledgment
                                    # Build response summary
                                    response_summary = f"✅ **Response Received!**\n" + f"**Action:** {response['action']}\n"
                                    
                                    # Add corrections if present
                                    if response.get('corrections', {}).get('primary_value'):
                                        response_summary += f"**Primary Value:** {response['corrections']['primary_value']}\n"
                                    if response.get('corrections', {}).get('suggested_values'):
                                        values = response['corrections']['suggested_values']
                                        if len(values) > 1:
                                            response_summary += f"**All Values:** {', '.join(values)}\n"
                                    
                                    response_summary += f"**Request ID:** `{request_id}`\n" + f"_Processing your response..._"
                                    
                                    await self.send_message(
                                        response_summary,
                                        channel=channel,
                                        thread_ts=thread_ts
                                    )
                                    
                                    # 🔥 COMPLETE THE HDL WORKFLOW!
                                    try:
                                        # Get agent coordinator from main app
                                        from app.main import agent_coordinator
                                        
                                        if agent_coordinator:
                                            # Route the human response to HDL Agent for completion
                                            completion_result = await agent_coordinator.route_message(
                                                source="SLACK_SERVICE",
                                                target="HDL_AGENT", 
                                                message={
                                                    "action": "process_human_response",
                                                    "data": {
                                                        "request_id": request_id,
                                                        "decision": response['action'],
                                                        "corrections": response.get('corrections', {}),
                                                        "feedback": response.get('feedback', text)
                                                    }
                                                }
                                            )
                                            
                                            # Send completion confirmation
                                            if completion_result.get("status") == "success":
                                                result_data = completion_result.get("result", {})
                                                decision = result_data.get("decision")
                                                execution_result = result_data.get("execution_result", {})
                                                
                                                if decision == "approve" or decision == "correct":
                                                    # Build completion summary
                                                    completion_summary = f"🎉 **Request Completed Successfully!**\n" + f"**Action:** {decision.title()}\n"
                                                    
                                                    # Add the values that were processed 
                                                    if response.get('corrections', {}).get('primary_value'):
                                                        completion_summary += f"**Applied Value:** {response['corrections']['primary_value']}\n"
                                                    
                                                    completion_summary += (
                                                        f"**Status:** {execution_result.get('status', 'completed')}\n" +
                                                        f"**Request ID:** `{request_id}`\n\n" +
                                                        f"✅ _Your response has been processed and the action has been completed._"
                                                    )
                                                    
                                                    await self.send_message(
                                                        completion_summary,
                                                        channel=channel,
                                                        thread_ts=thread_ts
                                                    )
                                                else:
                                                    await self.send_message(
                                                        f"🚫 **Request Rejected**\n" +
                                                        f"**Request ID:** `{request_id}`\n" +
                                                        f"**Status:** Action was rejected as requested\n\n" +
                                                        f"✅ _Your decision has been recorded._",
                                                        channel=channel,
                                                        thread_ts=thread_ts
                                                    )
                                            else:
                                                # Better error message for "Review request not found"
                                                error_msg = completion_result.get('message', 'Unknown error')
                                                details = completion_result.get('details', {})
                                                
                                                error_response = f"❌ **Error Processing Response**\n\n"
                                                error_response += f"**Request ID:** `{request_id}`\n"
                                                error_response += f"**Error:** {error_msg}\n\n"
                                                
                                                if "not found" in error_msg.lower():
                                                    error_response += (
                                                        "**What this means:**\n"
                                                        "This review request may have:\n"
                                                        "• Expired (requests are valid for a limited time)\n"
                                                        "• Already been processed\n"
                                                        "• Been lost due to an application restart\n\n"
                                                        "**What to do:**\n"
                                                        "Please request a new review if this action is still needed."
                                                    )
                                                else:
                                                    error_response += f"_Response recorded but may need manual review._"
                                                
                                                await self.send_message(
                                                    error_response,
                                                    channel=channel,
                                                    thread_ts=thread_ts
                                                )
                                        else:
                                            await self.send_message(
                                                f"❌ **System Error**\n" +
                                                f"**Issue:** Agent coordinator not available\n" +
                                                f"**Request ID:** `{request_id}`\n" +
                                                f"**Action:** Response recorded but needs manual processing",
                                                channel=channel,
                                                thread_ts=thread_ts
                                            )
                                            
                                    except Exception as completion_error:
                                        logger.error(f"Error completing HDL workflow: {completion_error}")
                                        await self.send_message(
                                            f"❌ **Processing Error**\n" +
                                            f"**Request ID:** `{request_id}`\n" +
                                            f"**Error:** {str(completion_error)}\n" +
                                            f"**Action:** Response recorded but needs manual review",
                                            channel=channel,
                                            thread_ts=thread_ts
                                        )
                                    
                                    logger.info(f"HDL Agent response completed: {request_id} -> {response['action']}")
                                    
                                else:
                                    await self.send_message(
                                        "❌ Could not extract Request ID from the original message",
                                        channel=channel,
                                        thread_ts=thread_ts
                                    )
                            except Exception as e:
                                logger.error(f"Error processing HDL Agent response: {str(e)}")
                                await self.send_message(
                                    f"❌ Error processing HDL response: {str(e)}",
                                    channel=channel,
                                    thread_ts=thread_ts
                                )
                        
                        # Handle document processing approvals (existing logic)
                        elif "Drive Link:" in parent_text:
                            file_id = parent_text.split("Drive Link:")[-1].split("/")[-1].strip()
                            
                            if file_id and self.handler_vector:
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
                                    logger.error(f"Error processing document approval: {str(e)}")
                                    await self.send_message(
                                        f"❌ Error processing approval: {str(e)}",
                                        channel=channel,
                                        thread_ts=thread_ts
                                    )
                            else:
                                await self.send_message(
                                    "❌ Could not find file ID or handler not available",
                                    channel=channel,
                                    thread_ts=thread_ts
                                )
                        else:
                            await self.send_message(
                                "❌ Could not identify the type of review request",
                                channel=channel,
                                thread_ts=thread_ts
                            )
                    return

            # Handle other messages (non-approval related)
            logger.info(f"💬 Processing as general message - thread_ts: {thread_ts}")
            bot_user_id = self.client.auth_test()["user_id"]
            is_mentioned = f"<@{bot_user_id}>" in text
            
            # 🔥 NEW: Check if this might be a response to a recent HDL review request
            # even if not threaded properly
            if not thread_ts and not is_mentioned:
                response = await self._parse_human_response(text)
                if response["action"] in ["approve", "correct", "reject"]:
                    logger.info(f"🎯 Detected HDL response pattern without thread: {response['action']}")
                    
                    # Look for recent HDL Agent messages in this channel (last 10 messages)
                    try:
                        recent_messages = self.client.conversations_history(
                            channel=channel,
                            limit=10
                        )
                        
                        if recent_messages["ok"]:
                            for msg in recent_messages["messages"]:
                                if (msg.get("bot_id") and 
                                    "Request ID:" in msg.get("text", "") and
                                    "HUMAN REVIEW REQUESTED" in msg.get("text", "")):
                                    
                                    logger.info(f"🎯 Found recent HDL request in channel, treating as response")
                                    # Extract request_id
                                    parent_text = msg.get("text", "")
                                    request_id = None
                                    for line in parent_text.split('\n'):
                                        if "Request ID:" in line:
                                            request_id = line.split('`')[1] if '`' in line else line.split(':')[1].strip()
                                            break
                                    
                                    if request_id:
                                        # Build response summary for fallback case
                                        fallback_summary = f"✅ **Response Received!**\n" + f"**Action:** {response['action']}\n"
                                        
                                        # Add corrections if present
                                        if response.get('corrections', {}).get('primary_value'):
                                            fallback_summary += f"**Primary Value:** {response['corrections']['primary_value']}\n"
                                        
                                        fallback_summary += (
                                            f"**Request ID:** `{request_id}`\n" +
                                            f"_Processing your response..._\n\n" +
                                            f"💡 _Tip: Next time, reply in the thread for faster processing!_"
                                        )
                                        
                                        await self.send_message(
                                            fallback_summary,
                                            channel=channel
                                        )
                                        
                                        # 🔥 COMPLETE THE HDL WORKFLOW for fallback case too!
                                        try:
                                            from app.main import agent_coordinator
                                            
                                            if agent_coordinator:
                                                completion_result = await agent_coordinator.route_message(
                                                    source="SLACK_SERVICE",
                                                    target="HDL_AGENT", 
                                                    message={
                                                        "action": "process_human_response",
                                                        "data": {
                                                            "request_id": request_id,
                                                            "decision": response['action'],
                                                            "entity_name": response.get('entity_name'),
                                                            "corrections": response.get('corrections', {}),
                                                            "original_text": text
                                                        }
                                                    }
                                                )
                                                
                                                if completion_result.get("status") == "success":
                                                    result_data = completion_result.get("result", {})
                                                    decision = result_data.get("decision")
                                                    execution_result = result_data.get("execution_result", {})
                                                    
                                                    if decision == "approve" or decision == "correct":
                                                        # Build completion summary for fallback
                                                        fallback_completion = f"🎉 **Request Completed Successfully!**\n" + f"**Action:** {decision.title()}\n"
                                                        
                                                        # Add the values that were processed 
                                                        if response.get('corrections', {}).get('primary_value'):
                                                            fallback_completion += f"**Applied Value:** {response['corrections']['primary_value']}\n"
                                                        
                                                        fallback_completion += (
                                                            f"**Status:** {execution_result.get('status', 'completed')}\n" +
                                                            f"**Request ID:** `{request_id}`"
                                                        )
                                                        
                                                        await self.send_message(
                                                            fallback_completion,
                                                            channel=channel
                                                        )
                                                    else:
                                                        await self.send_message(
                                                            f"🚫 **Request Rejected** - **Request ID:** `{request_id}`",
                                                            channel=channel
                                                        )
                                        except Exception as completion_error:
                                            logger.error(f"Error completing HDL workflow (fallback): {completion_error}")
                                        
                                        logger.info(f"HDL Agent response completed from channel message: {request_id} -> {response['action']}")
                                        return
                                    break
                    except Exception as e:
                        logger.error(f"Error checking for recent HDL messages: {e}")
            
            # 🔥 NEW: Check if this is a relevant question about entities, files, or system functionality
            # even without mention - more natural conversation
            text_lower = text.lower().strip()
            relevant_keywords = [
                # Entity-related questions
                "entities", "entity", "companies", "company", "organization", "organizations",
                "what entities", "list entities", "show entities", "existing entities",
                "entity names", "company names", "all entities", "how many entities",
                
                # File and system questions
                "files", "documents", "drive", "folder", "folders", "what files",
                "list files", "show files", "upload", "scan", "process",
                
                # Task-related questions  
                "tasks", "task", "todo", "what tasks", "list tasks", "show tasks",
                
                # General help
                "help", "what can you do", "capabilities", "functions", "features",
                "how to", "how do", "status", "health",
                
                # 🔥 NEW: Conversational follow-ups and natural language
                "did you get", "did that work", "are you there", "hello", "hi", "hey",
                "working?", "alive?", "ok?", "good?", "working", "alive",
                "thanks", "thank you", "got it", "okay", "yes", "no",
                "can you", "could you", "please", "would you",
                "what about", "how about", "what if", "is it", "are you",
                "do you", "will you", "response", "reply", "answer",
                "understand", "received", "processed", "completed"
            ]
            
            # Also check for contextual relevance - if bot was recently active, be more responsive
            is_contextually_relevant = False
            try:
                # Check if bot sent a message in the last 5 minutes in this channel
                recent_messages = self.client.conversations_history(
                    channel=channel,
                    limit=5,
                    oldest=(datetime.utcnow().timestamp() - 300)  # 5 minutes ago
                )
                
                if recent_messages["ok"]:
                    bot_user_id = self.client.auth_test()["user_id"]
                    for msg in recent_messages["messages"]:
                        if msg.get("user") == bot_user_id or msg.get("bot_id"):
                            is_contextually_relevant = True
                            logger.debug(f"🎯 Found recent bot activity, being more responsive to: {text}")
                            break
            except Exception as e:
                logger.debug(f"Error checking recent activity: {e}")
            
            is_relevant_question = (
                any(keyword in text_lower for keyword in relevant_keywords) or
                is_contextually_relevant
            )
            
            # Respond to:
            # 1. Direct mentions in any channel
            # 2. Direct messages (DM/IM channels)  
            # 3. Messages that start with the bot's name
            # 4. 🔥 NEW: Relevant questions about system functionality
            should_respond = (
                is_mentioned or 
                channel_type in ["im", "mpim"] or
                text.lower().startswith(("gabriel", "hey gabriel", "hi gabriel")) or
                is_relevant_question
            )
            
            if not should_respond:
                logger.debug(f"Ignoring message - not mentioned, not a DM, and not relevant. Channel type: {channel_type}")
                return

            logger.info(f"Processing message from user {user}: {text}")

            # Remove the bot mention from the text if present
            if is_mentioned:
                mention = f"<@{bot_user_id}>"
                text = text.replace(mention, "").strip()
                logger.debug(f"Removed bot mention. New text: {text}")

            # 🔥 NEW: Handle specific types of questions with appropriate responses
            
            # Entity-related questions
            if is_relevant_question and any(keyword in text_lower for keyword in [
                "entities", "entity names", "existing entities", "list entities", "all entities",
                "companies", "company names", "organizations"
            ]):
                logger.info(f"🎯 Handling entity-related question: {text}")
                try:
                    from app.main import agent_coordinator
                    
                    if agent_coordinator:
                        # Get list of entities
                        entities_result = await agent_coordinator.route_message(
                            source="SLACK_SERVICE",
                            target="DB_AGENT",
                            message={
                                "action": "list_entities",
                                "data": {}
                            }
                        )
                        
                        if entities_result.get("status") == "success":
                            entities = entities_result.get("result", [])
                            if entities:
                                entity_list = "\n".join([f"• **{entity.get('name', 'Unknown')}** (ID: {entity.get('entity_id', 'N/A')})" for entity in entities])
                                response_text = f"📋 **Current Entities in System:**\n\n{entity_list}\n\n📊 **Total:** {len(entities)} entities"
                            else:
                                response_text = "📋 **No entities found** in the system yet.\n\n💡 You can create entities by uploading documents or using the `/entities` API endpoint."
                        else:
                            response_text = f"❌ **Error retrieving entities:** {entities_result.get('message', 'Unknown error')}"
                        
                        await self.send_message(response_text, channel=channel)
                        return
                    else:
                        await self.send_message(
                            "❌ **System Error:** Agent coordinator not available. Please try again later.",
                            channel=channel
                        )
                        return
                        
                except Exception as e:
                    logger.error(f"Error handling entity question: {e}")
                    await self.send_message(
                        f"❌ **Error:** Could not retrieve entity information: {str(e)}",
                        channel=channel
                    )
                    return
            
            # 🔥 NEW: Conversational follow-ups and status checks
            elif is_relevant_question and any(keyword in text_lower for keyword in [
                "did you get", "did that work", "are you there", "working?", "alive?",
                "ok?", "good?", "working", "alive", "response", "received"
            ]):
                logger.info(f"🎯 Handling conversational follow-up: {text}")
                response_options = [
                    "Yes, I'm here and working! 👋 How can I help you?",
                    "All systems operational! ✅ What would you like me to do?",
                    "I'm alive and ready to assist! 🤖 What's next?",
                    "Yes, I received that! 📨 Everything's working fine on my end.",
                    "I'm here and listening! 👂 How can I help you today?"
                ]
                # Pick response based on the text content
                if "get" in text_lower or "received" in text_lower:
                    response_text = "Yes, I received that! 📨 Everything's working fine on my end."
                elif "work" in text_lower:
                    response_text = "All systems operational! ✅ What would you like me to do?"
                elif "there" in text_lower or "alive" in text_lower:
                    response_text = "I'm here and listening! 👂 How can I help you today?"
                else:
                    response_text = "Yes, I'm here and working! 👋 How can I help you?"
                
                await self.send_message(response_text, channel=channel)
                return
            
            # 🔥 NEW: Greetings and polite responses (ONLY for simple greetings)
            elif text_lower.strip() in ["hello", "hi", "hey", "thanks", "thank you", "got it", "okay"]:
                logger.info(f"🎯 Handling simple greeting: {text}")
                if any(word in text_lower for word in ["thank", "thanks"]):
                    response_text = "You're welcome! 😊 Anything else I can help you with?"
                elif any(word in text_lower for word in ["hello", "hi", "hey"]):
                    response_text = "Hello! 👋 I'm Gabriel Agent, your AI assistant. How can I help you today?"
                else:
                    response_text = "Great! 👍 Let me know if you need anything else."
                
                await self.send_message(response_text, channel=channel)
                return

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