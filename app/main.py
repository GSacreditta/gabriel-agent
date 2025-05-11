from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from .services.google_drive import GoogleDriveService
from .services.agent import create_agent
from .core.config import get_settings
from pydantic import BaseModel
import logging
import traceback
import sys
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from .services.ocr_service import OCRService

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

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

async def initialize_services():
    """Initialize all required services asynchronously."""
    global agent, drive_service
    try:
        # Initialize agent
        agent = create_agent()
        logger.info("Gabriel Agent initialized successfully")
        
        # Initialize drive service
        drive_service = GoogleDriveService()
        logger.info("Google Drive Service initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {str(e)}")
        logger.error(f"Traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")
        raise

async def process_document_background(file_id: str):
    """Background task for document processing."""
    try:
        logger.debug(f"Starting background document processing for file: {file_id}")
        input_params = {
            "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "agent_scratchpad": [],
            "file_id": file_id
        }
        await agent.ainvoke(input_params)
        logger.debug(f"Background document processing completed for file: {file_id}")
    except Exception as e:
        logger.error(f"Error in background document processing: {str(e)}")
        # Here you might want to implement retry logic or error reporting

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Application startup event triggered")
    try:
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
        # Add any cleanup tasks here
        logger.info("Shutdown tasks completed successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")
        logger.error(f"Traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")

@app.get("/")
async def root():
    """Root endpoint."""
    logger.debug("Root endpoint called")
    return {"message": "Welcome to Gabriel Agent Task Flow API"}

@app.get("/test-drive")
async def test_drive():
    """Test Google Drive connection."""
    try:
        logger.debug("Testing Google Drive connection")
        if not drive_service:
            raise HTTPException(status_code=503, detail="Drive service not initialized")
        
        files = await asyncio.to_thread(drive_service.get_folder_contents)
        return {"status": "success", "files": files}
    except Exception as e:
        logger.error(f"Error in test-drive endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error accessing Google Drive: {str(e)}"
        )

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Handle chat requests and route them to the appropriate intent handler."""
    try:
        logger.debug(f"Received chat request: {request.message}")
        
        if not agent:
            raise HTTPException(status_code=503, detail="Agent not initialized")
        
        # Determine request type
        calendar_keywords = ["calendar", "event", "schedule", "appointment", "meeting"]
        document_keywords = ["process", "classify", "organize", "file", "document", "upload"]
        
        is_calendar_request = any(keyword in request.message.lower() for keyword in calendar_keywords)
        is_document_request = any(keyword in request.message.lower() for keyword in document_keywords)
        
        # Prepare input parameters
        input_params = {
            "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "agent_scratchpad": [],
            "message": request.message
        }
        
        # Add drive_folder_id only for document requests
        if is_document_request and request.drive_folder_id:
            input_params["drive_folder_id"] = request.drive_folder_id
            logger.debug("Including drive_folder_id for document management request")
        
        # Get agent response
        response = await agent.ainvoke(input_params)
        logger.debug(f"Agent response: {response}")
        
        return ChatResponse(
            response=response.get("output", ""),
            status="success"
        )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        return ChatResponse(
            response="",
            status="error",
            error=str(e)
        )

@app.post("/process-document")
async def process_document(request: DocumentProcessRequest, background_tasks: BackgroundTasks):
    """Handle document processing requests."""
    try:
        logger.debug(f"Received document processing request for file: {request.file_id}")
        
        if not agent:
            raise HTTPException(status_code=503, detail="Agent not initialized")
        
        if request.background:
            # Add to background tasks
            background_tasks.add_task(process_document_background, request.file_id)
            return {"status": "processing", "message": "Document processing started in background"}
        
        # Process immediately
        input_params = {
            "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "agent_scratchpad": [],
            "file_id": request.file_id
        }
        
        response = await agent.ainvoke(input_params)
        logger.debug(f"Agent response for document processing: {response}")
        
        return {"status": "success", "response": response}
        
    except Exception as e:
        logger.error(f"Error in process-document endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    health_status = {
        "status": "healthy",
        "services": {
            "agent": agent is not None,
            "drive_service": drive_service is not None
        }
    }
    return health_status

@app.post("/test-ocr")
async def test_ocr(file_id: str):
    """
    Test endpoint for OCR functionality.
    
    Args:
        file_id (str): The Google Drive file ID to process
    """
    try:
        ocr_service = OCRService()
        
        # Test document processing
        result = await ocr_service.process_document(file_id)
        
        return {
            "success": True,
            "result": result
        }
    except Exception as e:
        logger.error(f"Error in test OCR endpoint: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 