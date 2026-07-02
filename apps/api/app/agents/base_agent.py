"""
Base Agent - Foundation class for all specialized agents
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from abc import ABC, abstractmethod


class BaseAgent(ABC):
    """Base class for all agents in the system"""
    
    def __init__(self, agent_type: str):
        self.agent_type = agent_type
        self.logger = logging.getLogger(f"agent.{agent_type}")
        self.activity_log = []
        self.coordinator = None
        
    @abstractmethod
    async def get_capabilities(self) -> List[str]:
        """Return list of agent capabilities"""
        pass
    
    @abstractmethod
    async def handle_message(self, source_agent: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming messages from other agents"""
        pass
    
    @abstractmethod
    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a specific task"""
        pass
    
    async def receive_message(self, source_agent: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Receive and handle messages from other agents"""
        return await self.handle_message(source_agent, message)

    async def send_message(self, target_agent: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send a message to another agent, routed through the coordinator.

        Agents (extraction, HDL, storage, file management) call this to reach
        each other; it delegates to AgentCoordinator.route_message. Returns an
        error dict instead of raising so callers can degrade gracefully.
        """
        if self.coordinator is None:
            self.logger.error(
                f"[{self.agent_type}] Cannot send message to {target_agent}: no coordinator set"
            )
            return {
                "status": "error",
                "message": f"{self.agent_type} has no coordinator reference - cannot reach {target_agent}",
            }
        return await self.coordinator.route_message(self.agent_type, target_agent, message)
    
    def log_activity(self, activity: str, details: Dict[str, Any] = None):
        """Log agent activity"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent": self.agent_type,
            "activity": activity,
            "details": details or {}
        }
        self.activity_log.append(log_entry)
        self.logger.info(f"[{self.agent_type}] {activity}: {details or ''}")
    
    def get_activity_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent activity log"""
        return self.activity_log[-limit:]
    
    def clear_activity_log(self):
        """Clear activity log"""
        self.activity_log.clear()
    
    def set_coordinator(self, coordinator):
        """Set the agent coordinator reference"""
        self.coordinator = coordinator