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
from pydantic import BaseModel
import logging
import traceback
import sys
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
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

async def initialize_services():
    """Initialize all required services asynchronously."""
    global agent, drive_service, slack_service, ocr_service, vector_service
    global file_discovery, document_processor, scheduler_service
    
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
            "scheduler_service": scheduler_service is not None
        }
    }
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
        
        # Run the integration test
        result = await test_document_processing_integration()
        
        if result["success"]:
            logger.info("Integration test completed successfully")
            return {
                "status": "success",
                "message": "Integration test completed successfully",
                "details": result
            }
        else:
            error_msg = f"Integration test failed: {result.get('error')}"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
            
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)