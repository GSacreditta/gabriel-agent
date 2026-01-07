"""
Agent Coordinator - Central coordination for Gabriel Agent Architecture
Orchestrates communication between all specialized agents
Manages agent lifecycle and message routing
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
import logging

from .base_agent import BaseAgent
from .file_management_agent import FileManagementAgent
from .extraction_agent import ExtractionAgent
from .storage_agent import StorageAgent
from .hdl_agent import HDLAgent
from .db_agent import DBAgent

logger = logging.getLogger(__name__)


class AgentCoordinator:
    """Central coordinator for all Gabriel agents"""
    
    def __init__(self):
        self.coordinator_id = "AGENT_COORDINATOR"
        
        # Initialize all agents
        self.agents = {}
        self.agent_instances = {}
        
        # Message routing
        self.message_queue = []
        self.message_history = []
        
        # Coordination state
        self.is_running = False
        self.startup_completed = False
        
        logger.info("Agent Coordinator initialized")
    
    async def initialize_agents(self) -> Dict[str, Any]:
        """Initialize all specialized agents"""
        try:
            logger.info("Initializing agents...")
            
            # Create agent instances
            self.agent_instances = {
                "DB_AGENT": DBAgent(),
                "FILE_MANAGEMENT_AGENT": FileManagementAgent(),
                "EXTRACTION_AGENT": ExtractionAgent(),
                "STORAGE_AGENT": StorageAgent(),
                "HDL_AGENT": HDLAgent()
            }
            
            # Initialize DB Agent without blocking database connection (lazy loading)
            logger.info("DB Agent created - database connection will be established on first use...")
            # Note: Database connection moved to lazy loading pattern for faster startup
            
            # PHASE III: Initialize File Management Agent with Google Drive service
            logger.info("Connecting File Management Agent to Google Drive...")
            try:
                from ..services.google_drive import GoogleDriveService
                drive_service = GoogleDriveService()
                self.agent_instances["FILE_MANAGEMENT_AGENT"].set_drive_service(drive_service)
                logger.info("✅ File Management Agent connected to Google Drive service")
            except Exception as e:
                logger.error(f"❌ Failed to connect Google Drive service: {e}")
                logger.warning("File Management Agent will run without Google Drive integration")
            
            # 🔥 NEW: Connect HDL Agent to Slack service
            logger.info("Connecting HDL Agent to Slack service...")
            try:
                # Import slack_service from the app's global state
                # We'll need to get this from the main app instance
                # For now, we'll add a method to set it after initialization
                logger.info("✅ HDL Agent ready for Slack connection (to be set by main app)")
            except Exception as e:
                logger.error(f"❌ Failed to connect Slack service: {e}")
                logger.warning("HDL Agent will run without Slack integration")
            
            # Set coordinator reference for each agent
            for agent_type, agent_instance in self.agent_instances.items():
                agent_instance.set_coordinator(self)
                self.agents[agent_type] = {
                    "instance": agent_instance,
                    "status": "initialized",
                    "capabilities": await agent_instance.get_capabilities()
                }
            
            # Initialize HDL Agent with database tables and restore pending reviews
            logger.info("Initializing HDL Agent with database persistence...")
            try:
                hdl_agent = self.agent_instances.get("HDL_AGENT")
                if hdl_agent and hasattr(hdl_agent, 'initialize_agent'):
                    await hdl_agent.initialize_agent()
                    logger.info("✅ HDL Agent initialization completed")
                else:
                    logger.warning("HDL Agent does not have initialize_agent method")
            except Exception as e:
                logger.error(f"❌ Failed to initialize HDL Agent: {e}")
                logger.warning("HDL Agent will continue without full initialization")
            
            # Connect agents to each other for direct communication
            await self.setup_agent_connections()
            
            self.startup_completed = True
            
            logger.info(f"All agents initialized successfully: {list(self.agents.keys())}")
            
            return {
                "status": "success",
                "agents_initialized": list(self.agents.keys()),
                "total_agents": len(self.agents)
            }
            
        except Exception as e:
            logger.error(f"Error initializing agents: {e}")
            return {"status": "error", "message": str(e)}
    
    async def setup_agent_connections(self):
        """Setup connections between agents for direct communication"""
        try:
            # Connect each agent to others
            for agent_type, agent_data in self.agents.items():
                agent_instance = agent_data["instance"]
                
                # Connect to other agents
                for other_type, other_data in self.agents.items():
                    if other_type != agent_type:
                        agent_instance.connect_agent(other_type, other_data["instance"])
            
            logger.info("Agent connections established")
            
        except Exception as e:
            logger.error(f"Error setting up agent connections: {e}")
    
    async def route_message(self, source: str, target: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Route message between agents"""
        try:
            if target not in self.agents:
                return {"status": "error", "message": f"Target agent {target} not found"}
            
            target_agent = self.agents[target]["instance"]
            
            # Log message routing
            logger.debug(f"Routing message: {source} -> {target}: {message.get('action', 'unknown')}")
            
            # Send message to target agent
            response = await target_agent.receive_message(source, message)
            
            # Store in message history
            self.message_history.append({
                "timestamp": datetime.utcnow().isoformat(),
                "source": source,
                "target": target,
                "message": message,
                "response": response
            })
            
            return response
            
        except Exception as e:
            logger.error(f"Error routing message from {source} to {target}: {e}")
            return {"status": "error", "message": str(e)}
    
    async def start_coordinator(self) -> Dict[str, Any]:
        """Start the agent coordinator"""
        try:
            if not self.startup_completed:
                init_result = await self.initialize_agents()
                if init_result.get("status") != "success":
                    return init_result
            
            self.is_running = True
            
            # Start agent health monitoring
            asyncio.create_task(self.monitor_agent_health())
            
            logger.info("Agent Coordinator started successfully")
            
            return {
                "status": "success",
                "message": "Agent Coordinator running",
                "agents_active": len(self.agents)
            }
            
        except Exception as e:
            logger.error(f"Error starting coordinator: {e}")
            return {"status": "error", "message": str(e)}
    
    async def stop_coordinator(self) -> Dict[str, Any]:
        """Stop the agent coordinator"""
        try:
            self.is_running = False
            
            # Update all agents status
            for agent_type, agent_data in self.agents.items():
                agent_data["status"] = "stopped"
            
            logger.info("Agent Coordinator stopped")
            
            return {"status": "success", "message": "Agent Coordinator stopped"}
            
        except Exception as e:
            logger.error(f"Error stopping coordinator: {e}")
            return {"status": "error", "message": str(e)}
    
    # High-level workflow orchestration
    async def process_document_workflow(self, document_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Orchestrate complete document processing workflow
        File Management -> Extraction -> Storage -> HDL Review
        """
        try:
            workflow_id = f"workflow_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            
            logger.info(f"Starting document workflow {workflow_id}")
            
            results = {
                "workflow_id": workflow_id,
                "status": "in_progress",
                "steps": {}
            }
            
            # Step 1: File Management - Validate and organize
            if document_data.get('entity_name'):
                file_mgmt_result = await self.route_message("COORDINATOR", "FILE_MANAGEMENT_AGENT", {
                    "action": "create_entity_folder",
                    "data": {"entity_name": document_data['entity_name']}
                })
                results["steps"]["file_management"] = file_mgmt_result
            
            # Step 2: Extraction - Process document content
            extraction_result = await self.route_message("COORDINATOR", "EXTRACTION_AGENT", {
                "action": "extract_document",
                "data": document_data
            })
            results["steps"]["extraction"] = extraction_result
            
            # Step 3: Storage - Vector storage handled automatically by Extraction Agent
            # (Storage Agent receives message from Extraction Agent)
            
            # Step 4: HDL Review - Human review handled automatically by Extraction Agent
            # (HDL Agent receives message from Extraction Agent)
            
            results["status"] = "completed"
            results["completed_at"] = datetime.utcnow().isoformat()
            
            logger.info(f"Document workflow {workflow_id} completed")
            
            return results
            
        except Exception as e:
            logger.error(f"Error in document workflow: {e}")
            return {"status": "error", "message": str(e), "workflow_id": workflow_id}
    
    async def process_entity_creation_workflow(self, entity_name: str) -> Dict[str, Any]:
        """
        Orchestrate entity creation workflow
        File Management -> DB Agent -> HDL Review
        """
        try:
            workflow_id = f"entity_workflow_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            
            logger.info(f"Starting entity creation workflow {workflow_id} for: {entity_name}")
            
            # Trigger File Management Agent to create entity folder
            # This will automatically trigger DB validation and HDL review if needed
            result = await self.route_message("COORDINATOR", "FILE_MANAGEMENT_AGENT", {
                "action": "create_entity_folder",
                "data": {"entity_name": entity_name}
            })
            
            return {
                "workflow_id": workflow_id,
                "entity_name": entity_name,
                "result": result,
                "status": "completed" if result.get("status") == "success" else "pending"
            }
            
        except Exception as e:
            logger.error(f"Error in entity creation workflow: {e}")
            return {"status": "error", "message": str(e)}
    
    # Agent management and monitoring
    async def get_agent_status(self, agent_type: Optional[str] = None) -> Dict[str, Any]:
        """Get status of specific agent or all agents"""
        try:
            if agent_type:
                if agent_type in self.agents:
                    agent_instance = self.agents[agent_type]["instance"]
                    return await agent_instance.get_status()
                else:
                    return {"status": "error", "message": f"Agent {agent_type} not found"}
            else:
                # Get status of all agents
                all_status = {}
                for agent_type, agent_data in self.agents.items():
                    agent_instance = agent_data["instance"]
                    all_status[agent_type] = await agent_instance.get_status()
                
                return {
                    "coordinator_status": "running" if self.is_running else "stopped",
                    "agents": all_status,
                    "total_agents": len(self.agents)
                }
                
        except Exception as e:
            logger.error(f"Error getting agent status: {e}")
            return {"status": "error", "message": str(e)}
    
    async def monitor_agent_health(self):
        """Monitor health of all agents"""
        while self.is_running:
            try:
                for agent_type, agent_data in self.agents.items():
                    agent_instance = agent_data["instance"]
                    is_healthy = await agent_instance.health_check()
                    
                    if not is_healthy:
                        logger.warning(f"Agent {agent_type} health check failed")
                        agent_data["status"] = "unhealthy"
                    else:
                        agent_data["status"] = "healthy"
                
                # Wait 30 seconds before next health check
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in health monitoring: {e}")
                await asyncio.sleep(30)
    
    async def execute_agent_task(self, agent_type: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task on a specific agent"""
        try:
            if agent_type not in self.agents:
                return {"status": "error", "message": f"Agent {agent_type} not found"}
            
            agent_instance = self.agents[agent_type]["instance"]
            result = await agent_instance.execute_task(task)
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing task on {agent_type}: {e}")
            return {"status": "error", "message": str(e)}
    
    # Utility methods
    async def get_message_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent message history"""
        return self.message_history[-limit:] if self.message_history else []
    
    async def get_agent_capabilities(self) -> Dict[str, List[str]]:
        """Get capabilities of all agents"""
        capabilities = {}
        for agent_type, agent_data in self.agents.items():
            capabilities[agent_type] = agent_data["capabilities"]
        
        return capabilities
    
    async def test_agent_communication(self) -> Dict[str, Any]:
        """Test communication between all agents"""
        try:
            test_results = {}
            
            for agent_type in self.agents.keys():
                # Test basic status check
                status = await self.get_agent_status(agent_type)
                test_results[agent_type] = {
                    "status_check": "pass" if status.get("agent_type") == agent_type else "fail",
                    "health_check": "pass" if await self.agents[agent_type]["instance"].health_check() else "fail"
                }
            
            return {
                "status": "completed",
                "test_results": test_results,
                "overall_health": all(
                    result["status_check"] == "pass" and result["health_check"] == "pass"
                    for result in test_results.values()
                )
            }
            
        except Exception as e:
            logger.error(f"Error testing agent communication: {e}")
            return {"status": "error", "message": str(e)}
    
    def set_slack_service(self, slack_service):
        """Connect Slack service to HDL Agent after initialization"""
        try:
            if "HDL_AGENT" in self.agent_instances:
                self.agent_instances["HDL_AGENT"].set_slack_service(slack_service)
                logger.info("✅ HDL Agent connected to Slack service")
                return True
            else:
                logger.error("❌ HDL Agent not found in agent instances")
                return False
        except Exception as e:
            logger.error(f"❌ Failed to connect Slack service to HDL Agent: {e}")
            return False 