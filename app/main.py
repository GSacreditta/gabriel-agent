from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from app.services.google_drive import GoogleDriveService
from app.services.agent import create_agent
from app.services.slack_service import SlackService
from app.services.ocr_service import OCRService
from app.services.vector_storage_service import VectorStorageService
from app.services.file_discovery_service import FileDiscoveryService
from app.services.document_processor import DocumentProcessorService
from app.services.scheduler_service import SchedulerService
from app.core.config import get_settings
from app.agents.agent_coordinator import AgentCoordinator
from pydantic import BaseModel
import logging
import traceback
import sys
import asyncio
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from app.services.embedding_service import EmbeddingService
from app.services.pdf_service import PDFService
from app.services.similarity_service import SimilarityService
from slack_sdk import WebClient
import os

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Output to console
        logging.FileHandler('app.log', mode='a')  # Append to file
    ]
)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
slack_client = WebClient(token=SLACK_BOT_TOKEN)

class ChatRequest(BaseModel):
    message: str
    drive_folder_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    status: str
    error: Optional[str] = None

class DocumentProcessRequest(BaseModel):
    file_id: str
    background: bool = False

class SlackEvent(BaseModel):
    """Model for Slack event payload."""
    type: str
    event: Dict[str, Any]
    challenge: Optional[str] = None
    token: Optional[str] = None
    team_id: Optional[str] = None

# New Agent-related Pydantic models
class EntityCreateRequest(BaseModel):
    name: str
    category: Optional[str] = None
    contact_info: Optional[str] = None
    notes: Optional[str] = None

class TaskCreateRequest(BaseModel):
    description: str
    type: Optional[str] = None
    entity_id: Optional[str] = None
    due_date: Optional[date] = None
    frequency: Optional[str] = None

class AgentMessageRequest(BaseModel):
    agent_type: str
    action: str
    data: Dict[str, Any] = {}

class AgentResponse(BaseModel):
    status: str
    result: Optional[Any] = None
    message: Optional[str] = None
    agent_type: Optional[str] = None

app = FastAPI(
    title="Gabriel Agent Task Flow",
    description="AI-powered personal assistant for managing structured tasks",
    version="0.1.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables
agent = None
drive_service = None
slack_service = None
ocr_service = None
vector_service = None
file_discovery = None
document_processor = None
scheduler_service = None
agent_coordinator = None

async def initialize_services():
    """Initialize all required services asynchronously."""
    global agent, drive_service, slack_service, ocr_service, vector_service
    global file_discovery, document_processor, scheduler_service, agent_coordinator
    
    try:
        # Initialize base services
        agent = create_agent()
        drive_service = GoogleDriveService()
        slack_service = SlackService()
        ocr_service = OCRService()
        pdf_service = PDFService()
        
        # Initialize Slack service with agent first
        logger.info("Initializing Slack service...")
        slack_init_success = await slack_service.initialize(agent)
        if not slack_init_success:
            logger.error("Failed to initialize Slack service")
            raise Exception("Failed to initialize Slack service")
        logger.info("Slack service initialized successfully")
        
        try:
            vector_service = VectorStorageService()
        except Exception as e:
            logger.error(f"Failed to initialize Vector Storage Service: {str(e)}")
            logger.warning("Continuing without Vector Storage Service")
            vector_service = None
        
        logger.info("Base services initialized successfully")
        
        # Initialize document processor service
        document_processor = DocumentProcessorService()
        await document_processor.initialize(
            ocr_service=ocr_service,
            pdf_service=pdf_service,
            vector_service=vector_service,
            drive_service=drive_service,
            agent=agent,
            slack_service=slack_service
        )
        logger.info("Document Processor Service initialized successfully")
        
        # Initialize file discovery service with document processor
        file_discovery = FileDiscoveryService()
        await file_discovery.initialize(drive_service, document_processor)
        logger.info("File Discovery Service initialized successfully")
        
        # Initialize and start scheduler last
        scheduler_service = SchedulerService()
        await scheduler_service.initialize(
            agent=agent,
            slack_service=slack_service,
            file_discovery=file_discovery
        )
        scheduler_service.start()
        logger.info("Scheduler Service initialized and started successfully")
        
        # Initialize Agent Coordinator (Phase II Integration)
        logger.info("Initializing Agent Coordinator...")
        agent_coordinator = AgentCoordinator()
        start_result = await agent_coordinator.start_coordinator()
        if start_result.get("status") != "success":
            logger.error(f"Failed to initialize Agent Coordinator: {start_result}")
            raise Exception(f"Failed to initialize Agent Coordinator: {start_result}")
        logger.info(f"Agent Coordinator initialized successfully with {start_result.get('agents_active', 0)} agents")
        
        # 🔥 NEW: Connect Slack service to HDL Agent
        if slack_service and agent_coordinator:
            logger.info("Connecting Slack service to HDL Agent...")
            slack_connected = agent_coordinator.set_slack_service(slack_service)
            if slack_connected:
                logger.info("✅ HDL Agent → Slack integration completed successfully!")
            else:
                logger.error("❌ Failed to connect Slack service to HDL Agent")
        else:
            logger.warning("⚠️ Cannot connect Slack to HDL Agent - services not initialized")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {str(e)}")
        logger.error(f"Traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")
        # Don't raise the error, just log it
        logger.warning("Continuing with limited functionality")

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Application startup event triggered")
    try:
        # Debug information
        import os
        import getpass
        logger.info(f"Current user: {getpass.getuser()}")
        
        # Set Google credentials environment variable if not set
        if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            credentials_path = os.path.join(os.getcwd(), "config", "credentials", "location-19291-fb284eccae8d.json")
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
            logger.info(f"Set GOOGLE_APPLICATION_CREDENTIALS to: {credentials_path}")
        
        logger.info(f"GOOGLE_APPLICATION_CREDENTIALS: {os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')}")
        logger.info(f"Current working directory: {os.getcwd()}")
        
        await initialize_services()
        logger.info("Startup tasks completed successfully")
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        logger.error(f"Traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Application shutdown event triggered")
    try:
        if scheduler_service:
            scheduler_service.stop()
            logger.info("Scheduler stopped successfully")
        if agent_coordinator:
            await agent_coordinator.stop_coordinator()
            logger.info("Agent Coordinator stopped successfully")
        logger.info("Shutdown tasks completed successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")
        logger.error(f"Traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")

@app.get("/")
async def root():
    """Root endpoint."""
    logger.debug("Root endpoint called")
    return {"message": "Welcome to Gabriel Agent Task Flow API"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    health_status = {
        "status": "healthy",
        "services": {
            "agent": agent is not None,
            "drive_service": drive_service is not None,
            "slack_service": slack_service is not None,
            "ocr_service": ocr_service is not None,
            "vector_service": vector_service is not None,
            "file_discovery": file_discovery is not None,
            "document_processor": document_processor is not None,
            "scheduler_service": scheduler_service is not None,
            "agent_coordinator": agent_coordinator is not None
        }
    }
    if agent_coordinator:
        # Add agent status details
        health_status["agents"] = await agent_coordinator.get_agent_status()
    return health_status

@app.get("/test-drive")
async def test_drive():
    """Run the document processing integration test."""
    try:
        logger.info("Starting document processing integration test")
        
        # Verify services are initialized
        if not all([agent, drive_service, slack_service, ocr_service, vector_service, 
                   file_discovery, document_processor, scheduler_service]):
            missing_services = []
            if not agent: missing_services.append("agent")
            if not drive_service: missing_services.append("drive_service")
            if not slack_service: missing_services.append("slack_service")
            if not ocr_service: missing_services.append("ocr_service")
            if not vector_service: missing_services.append("vector_service")
            if not file_discovery: missing_services.append("file_discovery")
            if not document_processor: missing_services.append("document_processor")
            if not scheduler_service: missing_services.append("scheduler_service")
            
            error_msg = f"Required services not initialized: {', '.join(missing_services)}"
            logger.error(error_msg)
            raise HTTPException(status_code=503, detail=error_msg)
        
        # Run Agent Coordinator test instead
        if agent_coordinator:
            # Test Agent Coordinator functionality
            agent_status = await agent_coordinator.get_agent_status()
            agent_test = await agent_coordinator.test_agent_communication()
            
            result = {
                "success": True,
                "agent_coordinator_active": True,
                "agents_status": agent_status,
                "communication_test": agent_test,
                "message": "Agent Coordinator integration test completed successfully"
            }
            
            logger.info("Agent Coordinator integration test completed successfully")
            return {
                "status": "success",
                "message": "Integration test completed successfully",
                "details": result
            }
        else:
            return {
                "status": "warning",
                "message": "Agent Coordinator not initialized, but other services are running",
                "details": {"agent_coordinator_active": False}
            }
            
    except HTTPException as he:
        raise he
    except Exception as e:
        error_msg = f"Unexpected error during integration test: {str(e)}"
        logger.error(error_msg)
        logger.error(f"Traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/slack/events")
async def slack_events(request: Request):
    """Handle incoming Slack events."""
    try:
        body = await request.json()
        logger.info(f"Received Slack event: {body}")

        # Handle URL verification
        if body.get("type") == "url_verification":
            logger.info("Handling Slack URL verification challenge")
            return {"challenge": body.get("challenge")}

        # Verify the event is from Slack
        if not slack_service:
            logger.error("Slack service not initialized")
            raise HTTPException(status_code=503, detail="Slack service not initialized")

        # Process the event
        event_type = body.get("type")
        if event_type == "event_callback":
            event = body.get("event", {})
            event_type = event.get("type")
            logger.info(f"Processing Slack event type: {event_type}")
            
            if event_type == "message":
                # Handle the event asynchronously
                logger.info("Creating task to handle message event")
                asyncio.create_task(slack_service._handle_message(event))
            else:
                logger.info(f"Unhandled event type: {event_type}")
            
            return {"status": "ok"}

        logger.info(f"Unhandled Slack event type: {event_type}")
        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error processing Slack event: {str(e)}")
        logger.error(f"Traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# PHASE II: AGENT COORDINATOR API ENDPOINTS
# ============================================================================

@app.get("/agents/status")
async def get_agents_status():
    """Get status of all agents in the Agent Coordinator."""
    try:
        if not agent_coordinator:
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        status = await agent_coordinator.get_agent_status()
        return {"status": "success", "result": status}
        
    except Exception as e:
        logger.error(f"Error getting agent status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agents/capabilities")
async def get_agents_capabilities():
    """Get capabilities of all agents."""
    try:
        if not agent_coordinator:
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        capabilities = await agent_coordinator.get_agent_capabilities()
        return {"status": "success", "result": capabilities}
        
    except Exception as e:
        logger.error(f"Error getting agent capabilities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agents/message", response_model=AgentResponse)
async def send_agent_message(request: AgentMessageRequest):
    """Send a message to a specific agent."""
    try:
        if not agent_coordinator:
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        response = await agent_coordinator.route_message(
            source="API",
            target=request.agent_type,
            message={
                "action": request.action,
                "data": request.data
            }
        )
        
        return AgentResponse(
            status=response.get("status", "unknown"),
            result=response.get("result"),
            message=response.get("message"),
            agent_type=request.agent_type
        )
        
    except Exception as e:
        logger.error(f"Error sending agent message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/entities", response_model=AgentResponse)
async def create_entity(request: EntityCreateRequest):
    """Create a new entity via DB Agent."""
    try:
        if not agent_coordinator:
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        response = await agent_coordinator.route_message(
            source="API",
            target="DB_AGENT",
            message={
                "action": "create_entity",
                "data": request.dict()
            }
        )
        
        return AgentResponse(
            status=response.get("status", "unknown"),
            result=response.get("result"),
            message=response.get("message"),
            agent_type="DB_AGENT"
        )
        
    except Exception as e:
        logger.error(f"Error creating entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/entities")
async def list_entities():
    """List all entities via DB Agent."""
    try:
        if not agent_coordinator:
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        response = await agent_coordinator.route_message(
            source="API",
            target="DB_AGENT",
            message={
                "action": "list_entities",
                "data": {}
            }
        )
        
        return {
            "status": response.get("status", "unknown"),
            "result": response.get("result", []),
            "count": len(response.get("result", []))
        }
        
    except Exception as e:
        logger.error(f"Error listing entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/entities/{entity_id}")
async def get_entity(entity_id: str):
    """Get a specific entity by ID via DB Agent."""
    try:
        if not agent_coordinator:
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        response = await agent_coordinator.route_message(
            source="API",
            target="DB_AGENT",
            message={
                "action": "get_entity",
                "data": {"entity_id": entity_id}
            }
        )
        
        if response.get("status") == "success" and response.get("result") is None:
            raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")
        
        return {
            "status": response.get("status", "unknown"),
            "result": response.get("result")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/entities/match")
async def match_entity(entity_name: str):
    """Match entity by exact name via DB Agent."""
    try:
        if not agent_coordinator:
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        response = await agent_coordinator.route_message(
            source="API",
            target="DB_AGENT",
            message={
                "action": "match_entity",
                "data": {"name": entity_name}
            }
        )
        
        return {
            "status": response.get("status", "unknown"),
            "result": response.get("result"),
            "found": response.get("result") is not None
        }
        
    except Exception as e:
        logger.error(f"Error matching entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tasks", response_model=AgentResponse)
async def create_task(request: TaskCreateRequest):
    """Create a new task via DB Agent."""
    try:
        if not agent_coordinator:
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        response = await agent_coordinator.route_message(
            source="API",
            target="DB_AGENT",
            message={
                "action": "create_task",
                "data": request.dict()
            }
        )
        
        return AgentResponse(
            status=response.get("status", "unknown"),
            result=response.get("result"),
            message=response.get("message"),
            agent_type="DB_AGENT"
        )
        
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tasks")
async def list_tasks(entity_id: Optional[str] = None, status: Optional[str] = None):
    """List tasks with optional filtering via DB Agent."""
    try:
        if not agent_coordinator:
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        response = await agent_coordinator.route_message(
            source="API",
            target="DB_AGENT",
            message={
                "action": "get_tasks",
                "data": {"entity_id": entity_id, "status": status}
            }
        )
        
        return {
            "status": response.get("status", "unknown"),
            "result": response.get("result", []),
            "count": len(response.get("result", [])),
            "filters": {"entity_id": entity_id, "status": status}
        }
        
    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/tasks/{task_id}/status")
async def update_task_status(task_id: str, status: str):
    """Update task status via DB Agent."""
    try:
        if not agent_coordinator:
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        # Validate status
        valid_statuses = ["Pending", "In Progress", "Done", "Cancel"]
        if status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
        
        response = await agent_coordinator.route_message(
            source="API",
            target="DB_AGENT",
            message={
                "action": "update_task_status",
                "data": {"task_id": task_id, "status": status}
            }
        )
        
        if response.get("status") == "success" and not response.get("result"):
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        
        return {
            "status": response.get("status", "unknown"),
            "result": {"task_id": task_id, "status": status, "updated": response.get("result", False)}
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating task status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/workflows/document-processing")
async def start_document_workflow(file_data: dict):
    """Start a document processing workflow via Agent Coordinator."""
    try:
        if not agent_coordinator:
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        response = await agent_coordinator.process_document_workflow(file_data)
        
        return {
            "status": response.get("status", "unknown"),
            "workflow_id": response.get("workflow_id"),
            "result": response,
            "message": "Document processing workflow started"
        }
        
    except Exception as e:
        logger.error(f"Error starting document workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/workflows/entity-creation")
async def start_entity_workflow(entity_name: str):
    """Start an entity creation workflow via Agent Coordinator."""
    try:
        if not agent_coordinator:
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        response = await agent_coordinator.process_entity_creation_workflow(entity_name)
        
        return {
            "status": response.get("status", "unknown"),
            "workflow_id": response.get("workflow_id"),
            "result": response,
            "message": f"Entity creation workflow started for: {entity_name}"
        }
        
    except Exception as e:
        logger.error(f"Error starting entity workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agents/test")
async def test_agent_communication():
    """Test communication between agents."""
    try:
        if not agent_coordinator:
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        response = await agent_coordinator.test_agent_communication()
        
        return {
            "status": "success",
            "result": response,
            "message": "Agent communication test completed"
        }
        
    except Exception as e:
        logger.error(f"Error testing agent communication: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# PHASE III: GOOGLE DRIVE INTEGRATION ENDPOINTS
# ============================================================================

@app.post("/files/scan")
async def scan_google_drive():
    """Scan Google Drive and update file inventory."""
    try:
        if not agent_coordinator:
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        response = await agent_coordinator.route_message(
            source="API",
            target="FILE_MANAGEMENT_AGENT",
            message={
                "action": "scan_files",
                "data": {}
            }
        )
        
        return {
            "status": response.get("status", "unknown"),
            "result": response.get("result"),
            "message": "Google Drive scan completed"
        }
        
    except Exception as e:
        logger.error(f"Error scanning Google Drive: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/files/inventory")
async def get_file_inventory():
    """Get complete file inventory report."""
    try:
        if not agent_coordinator:
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        response = await agent_coordinator.route_message(
            source="API",
            target="FILE_MANAGEMENT_AGENT",
            message={
                "action": "get_inventory",
                "data": {}
            }
        )
        
        return {
            "status": response.get("status", "unknown"),
            "result": response.get("result"),
            "message": "File inventory retrieved"
        }
        
    except Exception as e:
        logger.error(f"Error getting file inventory: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/files/{file_id}/move")
async def move_file(file_id: str, destination_folder_id: str):
    """Move a file to a specific folder in Google Drive."""
    try:
        if not agent_coordinator:
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        response = await agent_coordinator.route_message(
            source="API",
            target="FILE_MANAGEMENT_AGENT",
            message={
                "action": "move_file",
                "data": {
                    "file_id": file_id,
                    "destination_folder_id": destination_folder_id
                }
            }
        )
        
        return {
            "status": response.get("status", "unknown"),
            "result": response.get("result"),
            "message": f"File {file_id} move operation completed"
        }
        
    except Exception as e:
        logger.error(f"Error moving file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/files/{file_id}/metadata")
async def get_file_metadata(file_id: str):
    """Get detailed metadata for a specific file."""
    try:
        if not agent_coordinator:
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        response = await agent_coordinator.route_message(
            source="API",
            target="FILE_MANAGEMENT_AGENT",
            message={
                "action": "get_file_metadata",
                "data": {"file_id": file_id}
            }
        )
        
        return {
            "status": response.get("status", "unknown"),
            "result": response.get("result"),
            "message": f"Metadata retrieved for file {file_id}"
        }
        
    except Exception as e:
        logger.error(f"Error getting file metadata: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/files/{file_id}/download")
async def download_file(file_id: str):
    """Download a file from Google Drive to temporary location."""
    try:
        if not agent_coordinator:
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        response = await agent_coordinator.route_message(
            source="API",
            target="FILE_MANAGEMENT_AGENT",
            message={
                "action": "download_file",
                "data": {"file_id": file_id}
            }
        )
        
        return {
            "status": response.get("status", "unknown"),
            "result": response.get("result"),
            "message": f"File {file_id} download completed"
        }
        
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/folders/create/{entity_name}")
async def create_entity_folder(entity_name: str):
    """Create a folder for an entity (validates entity exists in DB first)."""
    try:
        if not agent_coordinator:
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        response = await agent_coordinator.route_message(
            source="API",
            target="FILE_MANAGEMENT_AGENT",
            message={
                "action": "create_entity_folder",
                "data": {"entity_name": entity_name}
            }
        )
        
        return {
            "status": response.get("status", "unknown"),
            "result": response.get("result"),
            "message": f"Entity folder creation for '{entity_name}' completed"
        }
        
    except Exception as e:
        logger.error(f"Error creating entity folder: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/files/organize")
async def organize_files_by_entity():
    """Organize files into entity folders based on content analysis."""
    try:
        if not agent_coordinator:
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        response = await agent_coordinator.route_message(
            source="API",
            target="FILE_MANAGEMENT_AGENT",
            message={
                "action": "organize_files_by_entity",
                "data": {}
            }
        )
        
        return {
            "status": response.get("status", "unknown"),
            "result": response.get("result"),
            "message": "File organization by entity completed"
        }
        
    except Exception as e:
        logger.error(f"Error organizing files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/drive/test")
async def test_google_drive_integration():
    """Test Google Drive integration end-to-end."""
    try:
        if not agent_coordinator:
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        test_results = {}
        
        # Test 1: Scan files
        logger.info("Testing Google Drive file scan...")
        scan_response = await agent_coordinator.route_message(
            source="API",
            target="FILE_MANAGEMENT_AGENT",
            message={"action": "scan_files", "data": {}}
        )
        test_results["scan_test"] = scan_response
        
        # Test 2: Get inventory
        logger.info("Testing inventory retrieval...")
        inventory_response = await agent_coordinator.route_message(
            source="API",
            target="FILE_MANAGEMENT_AGENT",
            message={"action": "get_inventory", "data": {}}
        )
        test_results["inventory_test"] = inventory_response
        
        # Test 3: Check Google Drive service connection
        file_mgmt_agent = agent_coordinator.agent_instances.get("FILE_MANAGEMENT_AGENT")
        test_results["drive_service_connected"] = file_mgmt_agent.drive_service is not None
        
        if file_mgmt_agent.drive_service:
            test_results["service_account"] = getattr(
                file_mgmt_agent.drive_service.credentials, 
                'service_account_email', 
                'unknown'
            )
        
        overall_status = "success" if all(
            test.get("status") == "success" for test in test_results.values() 
            if isinstance(test, dict) and "status" in test
        ) else "partial_success"
        
        return {
            "status": overall_status,
            "test_results": test_results,
            "message": "Google Drive integration test completed"
        }
        
    except Exception as e:
        logger.error(f"Error testing Google Drive integration: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ChromaDB Vector Storage Endpoints - Phase IV
@app.get("/chromadb/info")
async def get_chromadb_info():
    """Get ChromaDB collection information"""
    try:
        if not agent_coordinator:
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        response = await agent_coordinator.route_message(
            "API",
            "STORAGE_AGENT",
            {
                "action": "get_collection_info",
                "data": {}
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error getting ChromaDB info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chromadb/search")
async def search_chromadb(query: str, top_k: int = 5, entity_name: Optional[str] = None):
    """Perform similarity search in ChromaDB"""
    try:
        if not agent_coordinator:
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        # Prepare filter metadata if entity_name provided
        filter_metadata = {"entity_name": entity_name} if entity_name else None
        
        response = await agent_coordinator.route_message(
            "API",
            "STORAGE_AGENT",
            {
                "action": "similarity_search",
                "data": {
                    "query": query,
                    "top_k": top_k,
                    "filter_metadata": filter_metadata
                }
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error performing ChromaDB search: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chromadb/store")
async def store_in_chromadb(file_name: str, content: str, entity_name: Optional[str] = None):
    """Store document content in ChromaDB for testing"""
    try:
        if not agent_coordinator:
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        # Prepare mock extraction data for storage
        extraction_data = {
            "file_name": file_name,
            "entity_name": entity_name or "Test Entity",
            "subject": f"Test document: {file_name}",
            "summary": content[:200] + "..." if len(content) > 200 else content,
            "content": content,
            "document_type": "Test Document",
            "issue_date": datetime.now().isoformat(),
            "confidence_scores": {"subject": 0.95, "entity": 0.90},
            "processing_time": 1.5,
            "drive_link": f"https://drive.google.com/file/test_{file_name}"
        }
        
        response = await agent_coordinator.route_message(
            "API",
            "STORAGE_AGENT",
            {
                "action": "store_extraction",
                "data": extraction_data
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error storing in ChromaDB: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/chromadb/test")
async def test_chromadb_integration():
    """Test ChromaDB integration with Storage Agent"""
    try:
        if not agent_coordinator:
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        test_results = {}
        
        # Test 1: Get collection info
        logger.info("Testing ChromaDB collection info...")
        try:
            info_response = await agent_coordinator.route_message(
                "API",
                "STORAGE_AGENT",
                {
                    "action": "get_collection_info",
                    "data": {}
                }
            )
            test_results["collection_info_test"] = info_response
        except Exception as e:
            test_results["collection_info_test"] = {"status": "error", "message": str(e)}
        
        # Test 2: Store test document
        logger.info("Testing document storage...")
        try:
            test_doc = {
                "file_name": "test_document.pdf",
                "entity_name": "Acumulus Holdings",
                "subject": "Q4 2024 Financial Report",
                "summary": "This is a test financial report for Q4 2024 showing revenue growth and market expansion.",
                "content": "Full content of the financial report with detailed analysis of quarterly performance, revenue metrics, and strategic initiatives.",
                "document_type": "Financial Report",
                "issue_date": "2024-12-01",
                "confidence_scores": {"subject": 0.95, "entity": 0.92, "date": 0.88},
                "processing_time": 2.3,
                "drive_link": "https://drive.google.com/file/test_123"
            }
            
            store_response = await agent_coordinator.route_message(
                "API",
                "STORAGE_AGENT",
                {
                    "action": "store_extraction",
                    "data": test_doc
                }
            )
            test_results["document_storage_test"] = store_response
        except Exception as e:
            test_results["document_storage_test"] = {"status": "error", "message": str(e)}
        
        # Test 3: Perform similarity search
        logger.info("Testing similarity search...")
        try:
            search_response = await agent_coordinator.route_message(
                "API",
                "STORAGE_AGENT",
                {
                    "action": "similarity_search",
                    "data": {
                        "query": "financial report revenue",
                        "top_k": 3
                    }
                }
            )
            test_results["similarity_search_test"] = search_response
        except Exception as e:
            test_results["similarity_search_test"] = {"status": "error", "message": str(e)}
        
        # Test 4: Collection maintenance
        logger.info("Testing collection maintenance...")
        try:
            maintenance_response = await agent_coordinator.route_message(
                "API",
                "STORAGE_AGENT",
                {
                    "action": "collection_maintenance",
                    "data": {}
                }
            )
            test_results["maintenance_test"] = maintenance_response
        except Exception as e:
            test_results["maintenance_test"] = {"status": "error", "message": str(e)}
        
        # Determine overall status
        successful_tests = sum(1 for result in test_results.values() 
                             if isinstance(result, dict) and result.get("status") == "success")
        total_tests = len(test_results)
        
        overall_status = "success" if successful_tests == total_tests else "partial_success"
        
        return {
            "status": overall_status,
            "message": f"ChromaDB integration test completed ({successful_tests}/{total_tests} tests passed)",
            "test_results": test_results
        }
        
    except Exception as e:
        logger.error(f"Error testing ChromaDB integration: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# PHASE V: EXTRACTION AGENT API ENDPOINTS
# ============================================================================

@app.post("/extraction/extract-document")
async def extract_document_content(file_name: str, content: str, entity_name: Optional[str] = None):
    """Extract comprehensive document fields using Extraction Agent"""
    try:
        if not agent_coordinator:
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        # Prepare document data
        document_data = {
            "file_name": file_name,
            "content": content,
            "file_metadata": {
                "entity_name": entity_name,
                "source": "api_upload",
                "webViewLink": f"https://example.com/files/{file_name}"
            }
        }
        
        response = await agent_coordinator.route_message(
            "API",
            "EXTRACTION_AGENT",
            {
                "action": "extract_document",
                "data": document_data
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error extracting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/extraction/process-email")
async def process_email_content(
    subject: str, 
    content: str, 
    attachments: Optional[List[Dict[str, Any]]] = None
):
    """Process email content and attachments through Extraction Agent"""
    try:
        if not agent_coordinator:
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        # Prepare email data
        email_data = {
            "subject": subject,
            "content": content,
            "attachments": attachments or []
        }
        
        response = await agent_coordinator.route_message(
            "API",
            "EXTRACTION_AGENT",
            {
                "action": "process_email",
                "data": email_data
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing email: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/extraction/test")
async def test_extraction_integration():
    """Test Extraction Agent integration with sample documents"""
    try:
        if not agent_coordinator:
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        test_results = {}
        
        # Test 1: Financial document extraction
        logger.info("Testing financial document extraction...")
        try:
            financial_content = """
            ACUMULUS HOLDINGS Q4 2024 QUARTERLY REPORT
            
            Subject: Q4 2024 Financial Performance Update
            
            Dear Stakeholders,
            
            We are pleased to present our Q4 2024 financial results showing significant growth:
            - Revenue increased by 15% year-over-year
            - Net income rose to $2.3M from $1.8M in Q3
            - Market expansion into three new territories
            
            Action Required: Please review and provide feedback by January 15, 2025.
            
            Best regards,
            Financial Team
            """
            
            financial_response = await agent_coordinator.route_message(
                "API",
                "EXTRACTION_AGENT",
                {
                    "action": "extract_document",
                    "data": {
                        "file_name": "Acumulus_Q4_2024_Report.pdf",
                        "content": financial_content,
                        "file_metadata": {
                            "source": "test_extraction",
                            "document_type": "financial_report"
                        }
                    }
                }
            )
            test_results["financial_document_test"] = financial_response
        except Exception as e:
            test_results["financial_document_test"] = {"status": "error", "message": str(e)}
        
        # Test 2: Email processing
        logger.info("Testing email processing...")
        try:
            email_response = await agent_coordinator.route_message(
                "API",
                "EXTRACTION_AGENT",
                {
                    "action": "process_email",
                    "data": {
                        "subject": "Urgent: Board Meeting Documents Required",
                        "content": "Please provide the Q4 financial statements and budget proposals for the upcoming board meeting on January 20, 2025. All documents must be submitted by January 18, 2025.",
                        "attachments": [
                            {
                                "name": "budget_proposal.pdf",
                                "content": "BUDGET PROPOSAL 2025\n\nProposed budget allocation for fiscal year 2025...",
                                "password_protected": False
                            }
                        ]
                    }
                }
            )
            test_results["email_processing_test"] = email_response
        except Exception as e:
            test_results["email_processing_test"] = {"status": "error", "message": str(e)}
        
        # Determine overall status
        successful_tests = sum(1 for result in test_results.values() 
                             if isinstance(result, dict) and result.get("status") == "success")
        total_tests = len(test_results)
        
        overall_status = "success" if successful_tests == total_tests else "partial_success"
        
        return {
            "status": overall_status,
            "message": f"Phase V Extraction Agent test completed ({successful_tests}/{total_tests} tests passed)",
            "test_results": test_results,
            "capabilities_tested": [
                "comprehensive_document_extraction",
                "confidence_scoring",
                "document_type_classification", 
                "entity_extraction",
                "task_extraction",
                "email_processing",
                "hdl_review_submission"
            ]
        }
        
    except Exception as e:
        logger.error(f"Error testing extraction integration: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# DEBUG ENDPOINTS
# ============================================================================

@app.post("/debug/slack-response")
async def debug_slack_response(response_text: str):
    """Debug endpoint to test Slack response parsing."""
    try:
        if not slack_service:
            raise HTTPException(status_code=503, detail="Slack service not initialized")
        
        # Test the response parsing logic
        parsed_response = await slack_service._parse_human_response(response_text)
        
        return {
            "status": "success",
            "input_text": response_text,
            "parsed_response": parsed_response,
            "debug_info": {
                "input_length": len(response_text),
                "input_lower": response_text.lower().strip(),
                "detected_action": parsed_response.get("action"),
                "extracted_entity": parsed_response.get("entity_name")
            }
        }
        
    except Exception as e:
        logger.error(f"Error testing Slack response parsing: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)