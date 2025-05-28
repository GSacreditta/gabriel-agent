from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from app.services.google_drive import GoogleDriveService
from app.services.agent import create_agent
from app.services.slack_service import SlackService
from app.core.config import get_settings
from pydantic import BaseModel
import logging
import traceback
import sys
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from app.services.embedding_service import EmbeddingService
from app.services.ocr_service import OCRService
from app.services.pdf_service import PDFService
from app.services.similarity_service import SimilarityService
from app.services.scheduler_service import SchedulerService
from slack_sdk import WebClient
import os

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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
scheduler_service = None

async def initialize_services():
    """Initialize all required services asynchronously."""
    global agent, drive_service, slack_service, scheduler_service
    try:
        # Initialize agent
        agent = create_agent()
        logger.info("Gabriel Agent initialized successfully")
        
        # Initialize drive service
        drive_service = GoogleDriveService()
        logger.info("Google Drive Service initialized successfully")
        
        # Initialize Slack service
        slack_service = SlackService()
        logger.info("Slack Service initialized successfully")
        
        # Initialize and start scheduler
        scheduler_service = SchedulerService()
        await scheduler_service.initialize(drive_service, agent, slack_service)
        scheduler_service.start()
        logger.info("Scheduler Service initialized and started successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {str(e)}")
        logger.error(f"Traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")
        # Don't raise the error, just log it
        logger.warning("Continuing with limited functionality")

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
        # Debug information
        import os
        import getpass
        logger.info(f"Current user: {getpass.getuser()}")
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
        document_keywords = ["process", "classify", "organize", "file", "document", "upload"]
        
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

@app.post("/test-folder")
async def test_folder(entity_name: str):
    """
    Test endpoint for folder management.
    
    Args:
        entity_name (str): The entity name to create/match folder
    """
    try:
        if not drive_service:
            raise HTTPException(status_code=503, detail="Drive service not initialized")
        
        # Test folder creation/matching
        folder_result = await drive_service.create_or_match_folder(entity_name)
        
        return {
            "success": True,
            "folder_id": folder_result.get("folder_id"),
            "is_new": folder_result.get("is_new", False)
        }
    except Exception as e:
        logger.error(f"Error in test folder endpoint: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/test-document-flow")
async def test_document_flow(file_id: str):
    """
    Test endpoint for complete document processing flow.
    
    Args:
        file_id (str): The Google Drive file ID to process
    """
    try:
        if not drive_service:
            raise HTTPException(status_code=503, detail="Drive service not initialized")
        
        # 1. Process document with OCR
        ocr_service = OCRService()
        ocr_result = await ocr_service.process_document(file_id)
        
        if not ocr_result["success"]:
            raise Exception(f"OCR processing failed: {ocr_result.get('error')}")
        
        # 2. Extract entity name
        entity_name = ocr_result["data"]["extracted_fields"]["entity_name"]
        
        # 3. Create or match folder
        folder_result = await drive_service.create_or_match_folder(entity_name)
        
        # 4. Move file to folder
        move_result = await drive_service.move_file_to_folder(
            file_id=file_id,
            folder_id=folder_result["folder_id"]
        )
        
        return {
            "success": True,
            "ocr_result": ocr_result,
            "folder_result": folder_result,
            "move_result": move_result
        }
    except Exception as e:
        logger.error(f"Error in test document flow: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/test-embeddings")
async def test_embeddings(file_id: str):
    """
    Test endpoint for document embeddings generation.
    """
    try:
        logger.debug(f"Starting test-embeddings for file: {file_id}")
        
        # First, get the document content using existing services
        pdf_service = PDFService()
        result = await pdf_service.extract_text(file_id)
        
        if not result["success"]:
            # If PDF extraction fails, try OCR
            ocr_service = OCRService()
            result = await ocr_service.extract_text(file_id)
            
            if not result["success"]:
                raise Exception(f"Failed to extract text: {result.get('error')}")
        
        # Generate embeddings using the extracted text
        embedding_service = EmbeddingService(model_name="text-embedding-3-large")
        embedding_result = await embedding_service.generate_document_embeddings(
            text=result["text"],
            normalize=True,
            chunk_size=800,  # Custom chunk size
            chunk_overlap=150  # Custom overlap
        )
        
        return {
            "success": True,
            "text_length": len(result["text"]),
            "chunks": len(embedding_result.get("chunks", [])),
            "embedding_result": embedding_result
        }
        
    except Exception as e:
        logger.error(f"Error in test embeddings endpoint: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/test-pdf")
async def test_pdf(file_id: str):
    """
    Test endpoint for PDF text extraction.
    
    Args:
        file_id (str): The Google Drive file ID to process
    """
    try:
        pdf_service = PDFService()
        
        # Test PDF text extraction
        result = await pdf_service.extract_text(file_id)
        
        if result["success"] and result.get("is_scanned", False):
            # If the PDF appears to be scanned, try OCR
            ocr_service = OCRService()
            ocr_result = await ocr_service.extract_text(file_id)
            
            if ocr_result["success"]:
                result["text"] = ocr_result["text"]
                result["extraction_method"] = "ocr"
            else:
                result["extraction_method"] = "pdf"
        else:
            result["extraction_method"] = "pdf"
        
        return {
            "success": True,
            "result": result
        }
    except Exception as e:
        logger.error(f"Error in test PDF endpoint: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/process-document-enhanced")
async def process_document_enhanced(file_id: str):
    """Process a document with enhanced structured data extraction."""
    try:
        logger.debug(f"Starting enhanced document processing for file: {file_id}")
        
        if not agent:
            raise HTTPException(status_code=503, detail="Agent not initialized")
        
        # First, get the document content using OCR or PDF service
        pdf_service = PDFService()
        result = await pdf_service.extract_text(file_id)
        
        if not result["success"]:
            # If PDF extraction fails, try OCR
            ocr_service = OCRService()
            result = await ocr_service.extract_text(file_id)
            
            if not result["success"]:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to extract text from document: {result.get('error')}"
                )
        
        # Prepare input parameters for the agent
        input_params = {
            "input": f"Analyze this document and extract structured information:\n{result['text'][:1000]}..."
        }
        
        # Get agent response
        response = await agent.ainvoke(input_params)
        logger.debug(f"Raw agent response: {response}")
        
        # Extract JSON string from response
        try:
            import json
            from app.services.agent import DocumentInfo
            
            # Get the output string
            output_str = response.get("output", "")
            
            # Clean the output string
            output_str = output_str.strip()
            
            # Remove any markdown formatting
            if output_str.startswith("```json"):
                output_str = output_str[7:]
            if output_str.endswith("```"):
                output_str = output_str[:-3]
            output_str = output_str.strip()
            
            # Try to parse the JSON
            try:
                output_json = json.loads(output_str)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {str(e)}")
                logger.error(f"Attempted to parse: {output_str}")
                raise ValueError(f"Invalid JSON format: {str(e)}")
            
            # Parse into DocumentInfo
            output = DocumentInfo.parse_obj(output_json)
            
        except Exception as e:
            logger.error(f"Error parsing agent response: {str(e)}")
            logger.error(f"Raw response: {response.get('output', '')}")
            raise HTTPException(
                status_code=500,
                detail=f"Error parsing agent response: {str(e)}"
            )
            
        logger.debug(f"Enhanced document processing completed for file: {file_id}")
        
        return {
            "status": "success",
            "file_id": file_id,
            "extracted_data": output.dict(),
            "processing_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in enhanced document processing: {str(e)}")
        logger.error(f"Traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing document: {str(e)}"
        )

@app.post("/test-similarity")
async def test_similarity(file_id: str, query: str):
    """
    Test endpoint for similarity search.
    
    Args:
        file_id (str): The Google Drive file ID to search in
        query (str): The search query
    """
    try:
        logger.debug(f"Starting similarity search for file: {file_id} with query: {query}")
        
        # First, get the document content and generate embeddings
        pdf_service = PDFService()
        result = await pdf_service.extract_text(file_id)
        
        if not result["success"]:
            # If PDF extraction fails, try OCR
            ocr_service = OCRService()
            result = await ocr_service.extract_text(file_id)
            
            if not result["success"]:
                raise Exception(f"Failed to extract text: {result.get('error')}")
        
        # Generate embeddings
        embedding_service = EmbeddingService(model_name="text-embedding-3-large")
        embedding_result = await embedding_service.generate_document_embeddings(
            text=result["text"],
            normalize=True,
            chunk_size=800,
            chunk_overlap=150
        )
        
        if not embedding_result["success"]:
            raise Exception(f"Failed to generate embeddings: {embedding_result.get('error')}")
        
        # Perform similarity search
        similarity_service = SimilarityService()
        search_result = await similarity_service.find_similar_chunks(
            query=query,
            chunks=embedding_result["chunks"],
            top_k=3,
            similarity_threshold=0.7
        )
        
        return {
            "success": True,
            "query": query,
            "text_length": len(result["text"]),
            "total_chunks": len(embedding_result["chunks"]),
            "search_results": search_result
        }
        
    except Exception as e:
        logger.error(f"Error in similarity search: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/slack/events")
async def slack_events(request: Request):
    logger.info("Received a request at /slack/events")
    body = await request.json()
    logger.debug(f"Request body: {body}")
    
    if body.get("type") == "url_verification":
        logger.info("Handling URL verification request")
        return {"challenge": body.get("challenge")}
        
    if body.get("type") == "event_callback":
        event = body.get("event", {})
        logger.info(f"Event received: {event}")
        
        if event.get("type") == "message" and not event.get("bot_id"):
            user_message = event.get("text")
            channel = event["channel"]
            logger.info(f"Processing message from channel {channel}: {user_message}")
            
            try:
                if not agent:
                    logger.error("Agent not initialized")
                    await slack_service.send_message(
                        message="Sorry, I'm not properly initialized yet. Please try again in a moment.",
                        channel=channel
                    )
                    return {"status": "error", "message": "Agent not initialized"}
                
                # Get response from your agent
                logger.info("Getting response from agent")
                agent_response = await agent.process_message(user_message)
                logger.info(f"Agent response: {agent_response}")
                
                # Send the response back to Slack
                logger.info("Sending response to Slack")
                await slack_service.send_message(
                    message=agent_response,
                    channel=channel
                )
                logger.info("Response sent successfully")
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                logger.error(f"Traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")
                await slack_service.send_message(
                    message="Sorry, I encountered an error processing your message.",
                    channel=channel
                )
                
    return {"status": "ok"}

@app.post("/slack/chat")
async def slack_chat(message: str, channel: str = None):
    """Send a message to Slack."""
    try:
        if not slack_service:
            raise HTTPException(status_code=503, detail="Slack service not initialized")
            
        response = await slack_service.send_review_request(message, channel)
        if not response["success"]:
            raise HTTPException(status_code=500, detail=response["error"])
            
        return {"status": "success", "response": response["response"]}
        
    except Exception as e:
        logger.error(f"Error in slack-chat endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error sending message to Slack: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)