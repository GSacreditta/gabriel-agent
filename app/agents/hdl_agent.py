"""
HDL Agent - Human-Device Interface Agent
Manages human interaction workflow for approvals and reviews via Slack
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import uuid
import json
from .base_agent import BaseAgent


class HDLAgent(BaseAgent):
    """Human-Device Interface Agent for human approvals and reviews"""
    
    def __init__(self):
        super().__init__("HDL_AGENT")
        
        # Review queue management
        self.pending_reviews = {}  # request_id -> review_data
        self.completed_reviews = {}
        
        # Slack service integration
        self.slack_service = None
        
        # Timeout configuration
        self.review_timeout_hours = 12
        
    def set_slack_service(self, slack_service):
        """Set the Slack service for sending messages"""
        self.slack_service = slack_service
        self.logger.info("Slack service connected to HDL Agent")
    
    def connect_agent(self, agent_type: str, agent_instance):
        """Connect to another agent"""
        self.log_activity(f"Connected to {agent_type}", {"agent_type": agent_type})
    
    async def health_check(self) -> bool:
        """Check if the agent is healthy"""
        try:
            # Basic health check - agent is healthy if slack service is available
            return self.slack_service is not None
        except Exception as e:
            self.log_activity("Health check failed", {"error": str(e)})
            return False
        
    async def get_capabilities(self) -> List[str]:
        """Return HDL Agent capabilities"""
        return [
            "human_review_workflow",
            "approval_management",
            "timeout_handling", 
            "slack_interaction",
            "decision_execution"
        ]
    
    async def handle_message(self, source_agent: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle messages from other agents"""
        action = message.get('action')
        data = message.get('data', {})
        
        try:
            if action == "request_review":
                result = await self.request_human_review(source_agent, data)
                return {"status": "success", "result": result}
                
            elif action == "process_human_response":
                result = await self.process_human_response(data)
                return {"status": "success", "result": result}
                
            else:
                return {"status": "error", "message": f"Unknown action: {action}"}
                
        except Exception as e:
            self.logger.error(f"Error handling message: {e}")
            return {"status": "error", "message": str(e)}
    
    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute HDL tasks"""
        task_type = task.get('type')
        
        if task_type == "timeout_check":
            return await self.check_review_timeouts()
        else:
            return {"status": "error", "message": f"Unknown task type: {task_type}"}
    
    async def _persist_review_to_db(self, review_data: Dict[str, Any]) -> bool:
        """Persist review data to database for durability"""
        try:
            if not self.coordinator:
                self.logger.warning("No coordinator available for database persistence")
                return False
                
            # Send to DB agent to store the review
            db_result = await self.send_message("DB_AGENT", {
                "action": "execute_command",
                "data": {
                    "query": """
                        INSERT INTO hdl_reviews (
                            request_id, source_agent, request_type, data, 
                            message, status, created_at, expires_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (request_id) DO UPDATE SET
                            status = EXCLUDED.status,
                            data = EXCLUDED.data
                    """,
                    "params": [
                        review_data['request_id'],
                        review_data['source_agent'], 
                        review_data['request_type'],
                        json.dumps(review_data['data']),
                        review_data['message'],
                        review_data['status'],
                        review_data['created_at'],
                        review_data['expires_at']
                    ]
                }
            })
            
            if db_result.get('status') == 'success':
                self.logger.info(f"✅ Review persisted to DB: {review_data['request_id']}")
                return True
            else:
                self.logger.error(f"❌ Failed to persist review: {db_result.get('message')}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error persisting review to DB: {e}")
            return False
    
    async def _load_review_from_db(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Load review data from database"""
        try:
            if not self.coordinator:
                self.logger.warning("No coordinator available for database access")
                return None
                
            # Query DB agent for the review
            db_result = await self.send_message("DB_AGENT", {
                "action": "execute_query", 
                "data": {
                    "query": """
                        SELECT request_id, source_agent, request_type, data, 
                               message, status, created_at, expires_at
                        FROM hdl_reviews 
                        WHERE request_id = %s
                    """,
                    "params": [request_id]
                }
            })
            
            if db_result.get('status') == 'success' and db_result.get('result'):
                rows = db_result['result']
                if rows:
                    row = rows[0]
                    review_data = {
                        'request_id': row[0],
                        'source_agent': row[1],
                        'request_type': row[2],
                        'data': json.loads(row[3]) if row[3] else {},
                        'message': row[4],
                        'status': row[5],
                        'created_at': row[6],
                        'expires_at': row[7]
                    }
                    self.logger.info(f"✅ Review loaded from DB: {request_id}")
                    return review_data
                    
            self.logger.warning(f"⚠️ Review not found in DB: {request_id}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error loading review from DB: {e}")
            return None
    
    async def _ensure_hdl_reviews_table(self):
        """Ensure the hdl_reviews table exists"""
        try:
            if not self.coordinator:
                return False
                
            db_result = await self.send_message("DB_AGENT", {
                "action": "execute_command",
                "data": {
                    "query": """
                        CREATE TABLE IF NOT EXISTS hdl_reviews (
                            request_id VARCHAR(255) PRIMARY KEY,
                            source_agent VARCHAR(100) NOT NULL,
                            request_type VARCHAR(100),
                            data TEXT,
                            message TEXT,
                            status VARCHAR(50) DEFAULT 'pending',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            expires_at TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            response_data TEXT
                        )
                    """,
                    "params": []
                }
            })
            
            return db_result.get('status') == 'success'
            
        except Exception as e:
            self.logger.error(f"Error creating hdl_reviews table: {e}")
            return False

    async def request_human_review(self, source_agent: str, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Request human review for an action"""
        try:
            request_id = str(uuid.uuid4())
            
            review_data = {
                'request_id': request_id,
                'source_agent': source_agent,
                'request_type': request_data.get('type'),
                'data': request_data,
                'message': request_data.get('message', 'Review requested'),
                'status': 'pending',
                'created_at': datetime.utcnow(),
                'expires_at': datetime.utcnow() + timedelta(hours=12)
            }
            
            # Store in memory
            self.pending_reviews[request_id] = review_data
            
            # 🔥 NEW: Persist to database for durability
            await self._ensure_hdl_reviews_table()
            await self._persist_review_to_db(review_data)
            
            # Send to Slack
            if self.slack_service:
                slack_message = self._format_review_message(review_data)
                slack_result = await self.slack_service.send_message(
                    text=slack_message,
                    channel=None  # Uses default channel
                )
                
                if slack_result.get("success"):
                    review_data['slack_message_ts'] = slack_result.get("message_ts")
                    review_data['slack_channel'] = slack_result.get("channel")
                    self.logger.info(f"✅ Review request sent to Slack: {request_id}")
                else:
                    self.logger.error(f"❌ Failed to send Slack message: {slack_result.get('error')}")
            else:
                self.logger.warning("⚠️ Slack service not connected - review request stored but not sent")
            
            self.log_activity("Human review requested", {
                "request_id": request_id,
                "type": request_data.get('type'),
                "source_agent": source_agent,
                "slack_sent": self.slack_service is not None
            })
            
            return {
                "request_id": request_id,
                "status": "pending",
                "message": "Review request submitted to human"
            }
            
        except Exception as e:
            self.logger.error(f"Error requesting human review: {e}")
            return {"status": "error", "message": str(e)}
    
    def _format_review_message(self, review_data: Dict[str, Any]) -> str:
        """Format review request for Slack message"""
        request_type = review_data.get('request_type', 'Unknown')
        entity_name = review_data['data'].get('entity_name', 'Unknown Entity')
        message = review_data['data'].get('message', 'Review requested')
        request_id = review_data['request_id']
        
        slack_message = f"""
🔍 **HUMAN REVIEW REQUESTED**

**Request ID:** `{request_id}`
**Type:** {request_type}
**Entity:** {entity_name}
**Details:** {message}

**Please respond in this thread with your feedback:**

You can simply say things like:
• **To approve:** "yes", "looks good", "approve it", "ok"
• **To approve with changes:** "approve as Microsoft", "yes but call it Apple Inc"
• **To correct:** "change it to Google", "it should be Amazon", "fix the name to Tesla"
• **To reject:** "no", "reject", "that's wrong", "don't approve"

_I understand natural language, so just respond however feels natural to you!_ 😊

⏰ **Expires:** {review_data['expires_at'].strftime('%Y-%m-%d %H:%M:%S')} UTC
        """.strip()
        
        return slack_message
    
    async def process_human_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process human response to review request"""
        try:
            request_id = response_data.get('request_id')
            human_decision = response_data.get('decision')  # approve, reject
            
            # First try to find in memory
            review_data = self.pending_reviews.get(request_id)
            
            # If not in memory, try loading from database
            if not review_data:
                self.logger.info(f"🔍 Review not in memory, loading from DB: {request_id}")
                review_data = await self._load_review_from_db(request_id)
                
                if review_data:
                    # Add back to memory for processing
                    self.pending_reviews[request_id] = review_data
                    self.logger.info(f"✅ Review restored from DB to memory: {request_id}")
                
            if not review_data:
                return {"status": "error", "message": "Review request not found"}
            
            review_data['status'] = human_decision
            review_data['human_response'] = response_data
            
            # Move to completed
            self.completed_reviews[request_id] = review_data
            if request_id in self.pending_reviews:
                del self.pending_reviews[request_id]
            
            # 🔥 Update status in database
            await self._persist_review_to_db(review_data)
            
            # Execute action based on decision
            if human_decision in ["approve", "correct"]:
                # Both "approve" and "correct" should execute the action 
                # For "correct", we'll use the corrected values from response_data
                if human_decision == "correct" and response_data.get('corrections'):
                    corrections = response_data['corrections']
                    
                    # Apply the primary value if available (backwards compatibility)
                    if corrections.get('primary_value'):
                        # For entity corrections, update the entity name
                        if 'entity_name' in review_data['data']:
                            review_data['data']['entity_name'] = corrections['primary_value']
                        
                        # Store all corrections for the downstream system to use
                        review_data['human_corrections'] = corrections
                    
                    # Store the original human feedback for context
                    if response_data.get('feedback'):
                        review_data['human_feedback'] = response_data['feedback']
                
                execution_result = await self.execute_approved_action(review_data)
            else:
                execution_result = {"status": "rejected", "message": "Action rejected by human"}
            
            self.log_activity("Human response processed", {
                "request_id": request_id,
                "decision": human_decision
            })
            
            return {
                "status": "completed",
                "decision": human_decision,
                "execution_result": execution_result
            }
            
        except Exception as e:
            self.logger.error(f"Error processing human response: {e}")
            return {"status": "error", "message": str(e)}
    
    async def execute_approved_action(self, review_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute approved action by coordinating with appropriate agent"""
        try:
            request_type = review_data['request_type']
            data = review_data['data']
            
            if request_type == "entity_creation":
                # Request DB Agent to create entity
                result = await self.send_message("DB_AGENT", {
                    "action": "create_entity",
                    "data": {
                        "name": data.get('entity_name'),
                        "category": data.get('category', 'General'),
                        "notes": "Created via HDL approval"
                    }
                })
                return result
                
            elif request_type == "file_deletion":
                # Mock file deletion execution
                return {"status": "completed", "message": "File deletion executed"}
                
            else:
                return {"status": "error", "message": f"Unknown action type: {request_type}"}
                
        except Exception as e:
            self.logger.error(f"Error executing approved action: {e}")
            return {"status": "error", "message": str(e)}
    
    async def check_review_timeouts(self) -> Dict[str, Any]:
        """Check for expired review requests and retry"""
        try:
            current_time = datetime.utcnow()
            expired_requests = []
            
            for request_id, review_data in list(self.pending_reviews.items()):
                if current_time > review_data['expires_at']:
                    expired_requests.append(request_id)
                    
                    # Create retry request
                    await self.create_retry_request(review_data)
                    
                    # Move to completed with timeout status
                    review_data['status'] = "timeout"
                    self.completed_reviews[request_id] = review_data
                    del self.pending_reviews[request_id]
            
            self.log_activity("Timeout check completed", {
                "expired_requests": len(expired_requests)
            })
            
            return {
                "status": "completed",
                "expired_requests": expired_requests,
                "retries_created": len(expired_requests)
            }
            
        except Exception as e:
            self.logger.error(f"Error checking timeouts: {e}")
            return {"status": "error", "message": str(e)}
    
    async def create_retry_request(self, original_review: Dict[str, Any]):
        """Create retry request after timeout"""
        try:
            new_request_id = str(uuid.uuid4())
            
            retry_data = {
                'request_id': new_request_id,
                'source_agent': original_review['source_agent'],
                'request_type': original_review['request_type'],
                'data': original_review['data'],
                'message': f"RETRY: {original_review['message']} (Previous request timed out)",
                'status': 'pending',
                'created_at': datetime.utcnow(),
                'expires_at': datetime.utcnow() + timedelta(hours=12),
                'retry_of': original_review['request_id']
            }
            
            self.pending_reviews[new_request_id] = retry_data
            
            self.log_activity("Retry request created", {
                "original_request": original_review['request_id'],
                "retry_request": new_request_id
            })
            
        except Exception as e:
            self.logger.error(f"Error creating retry request: {e}") 