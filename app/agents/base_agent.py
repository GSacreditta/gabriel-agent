"""
Base Agent Class for Gabriel Agent Architecture
Provides common functionality and interface for all specialized agents
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
import uuid
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class AgentMessage(BaseModel):
    """Structured message format for inter-agent communication"""
    action: str
    data: Dict[str, Any]
    timestamp: datetime
    source: Optional[str] = None
    priority: int = Field(default=1, ge=1, le=10)  # Priority from 1-10
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class AgentState:
    """Represents the state of an agent"""
    
    def __init__(self, agent_id: str, agent_type: str):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.status = "initialized"
        self.last_activity = datetime.utcnow()
        self.context = {}
        self.pending_tasks = []
        self.completed_tasks = []
        
    def update_status(self, status: str):
        """Update agent status and last activity"""
        self.status = status
        self.last_activity = datetime.utcnow()
        
    def add_task(self, task: Dict[str, Any]):
        """Add a task to pending tasks"""
        task['id'] = str(uuid.uuid4())
        task['created_at'] = datetime.utcnow()
        task['status'] = 'pending'
        self.pending_tasks.append(task)
        
    def complete_task(self, task_id: str, result: Any = None):
        """Mark a task as completed"""
        for task in self.pending_tasks:
            if task['id'] == task_id:
                task['status'] = 'completed'
                task['completed_at'] = datetime.utcnow()
                task['result'] = result
                self.completed_tasks.append(task)
                self.pending_tasks.remove(task)
                break

class BaseAgent(ABC):
    """Base class for all Gabriel agents"""
    
    def __init__(self, agent_type: str):
        self.agent_id = str(uuid.uuid4())
        self.agent_type = agent_type
        self.state = AgentState(self.agent_id, agent_type)
        self.logger = logging.getLogger(f"{__name__}.{agent_type}")
        
        # Agent coordination
        self.coordinator = None
        self.connected_agents = {}
        
        self.logger.info(f"Initialized {agent_type} agent with ID: {self.agent_id}")
    
    def set_coordinator(self, coordinator):
        """Set the agent coordinator for inter-agent communication"""
        self.coordinator = coordinator
        
    def connect_agent(self, agent_type: str, agent_instance):
        """Connect to another agent for direct communication"""
        self.connected_agents[agent_type] = agent_instance
        
    async def send_message(self, target_agent: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send a message to another agent through the coordinator"""
        # Create validated message
        if not isinstance(message, AgentMessage):
            validated_message = AgentMessage(
                action=message.get('action', 'unknown'),
                data=message.get('data', {}),
                timestamp=message.get('timestamp', datetime.utcnow()),
                source=self.agent_type,
                priority=message.get('priority', 1)
            )
        else:
            validated_message = message
            
        if self.coordinator:
            return await self.coordinator.route_message(
                source=self.agent_type,
                target=target_agent,
                message=validated_message.model_dump()
            )
        else:
            raise Exception("No coordinator set for inter-agent communication")
    
    async def receive_message(self, source_agent: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Receive and process a message from another agent"""
        # Validate incoming message
        try:
            if not isinstance(message, AgentMessage):
                validated_message = AgentMessage(
                    action=message.get('action', 'unknown'),
                    data=message.get('data', {}),
                    timestamp=message.get('timestamp', datetime.utcnow()),
                    source=source_agent,
                    priority=message.get('priority', 1)
                )
            else:
                validated_message = message
                
            self.logger.info(f"Received message from {source_agent}: {validated_message.action} (priority: {validated_message.priority})")
            return await self.handle_message(source_agent, validated_message)
        except Exception as e:
            self.logger.error(f"Failed to validate message from {source_agent}: {e}")
            return {
                'status': 'error',
                'error': f'Invalid message format: {str(e)}'
            }
    
    @abstractmethod
    async def handle_message(self, source_agent: str, message: AgentMessage) -> Dict[str, Any]:
        """Handle incoming messages from other agents"""
        pass
    
    @abstractmethod
    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a specific task"""
        pass
    
    @abstractmethod
    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this agent provides"""
        pass
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current agent status"""
        return {
            'agent_id': self.agent_id,
            'agent_type': self.agent_type,
            'status': self.state.status,
            'last_activity': self.state.last_activity.isoformat(),
            'pending_tasks': len(self.state.pending_tasks),
            'completed_tasks': len(self.state.completed_tasks),
            'capabilities': await self.get_capabilities()
        }
    
    def log_activity(self, activity: str, details: Dict[str, Any] = None):
        """Log agent activity"""
        self.state.update_status("active")
        self.logger.info(f"{self.agent_type} - {activity}: {details or ''}")
        
    async def health_check(self) -> bool:
        """Check if agent is healthy and responsive"""
        try:
            self.state.update_status("healthy")
            return True
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            self.state.update_status("unhealthy")
            return False
