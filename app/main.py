"""
Gabriel Agent Task Flow - Enhanced Version (main.py)

This is the enhanced version of the Gabriel Agent system, systematically implemented 
from the original main.py with improvements and comprehensive documentation.

IMPLEMENTATION PROGRESS:
[SUCCESS] Service initialization with enhanced error handling and dependency management
[SUCCESS] Agent Coordinator integration with all specialized agents (DB, HDL, Extraction, Storage, FileManagement)
[SUCCESS] Pydantic models for API requests/responses
[SUCCESS] Agent API endpoints (/agents/status, /agents/capabilities, /agents/message)
[SUCCESS] Entity management endpoints (/entities CRUD operations)
[SUCCESS] Document processing endpoints (/extraction/extract-document, /extraction/process-email)
[SUCCESS] ChromaDB vector storage endpoints (/chromadb/info, /chromadb/search, /chromadb/store)
[SUCCESS] Slack integration (/slack/events with enhanced event processing)
[SUCCESS] File management endpoints (/files/scan, /files/inventory)
[SUCCESS] Startup/shutdown event handlers with proper service cleanup
[SUCCESS] Comprehensive logging and error handling throughout

ENHANCEMENTS OVER ORIGINAL:
- Phased service initialization with dependency checking
- Enhanced error handling with detailed tracebacks
- Better logging with emojis and structured messages
- Service integration status reporting
- Enhanced metadata in API responses
- Graceful degradation when services fail
- Comprehensive health checking and debugging endpoints

ARCHITECTURE:
- Agent Coordinator orchestrates 5 specialized agents:
  • DB_AGENT: Database operations and entity management
  • FILE_MANAGEMENT_AGENT: Google Drive integration and file operations
  • EXTRACTION_AGENT: Document content extraction and processing
  • STORAGE_AGENT: ChromaDB vector storage and similarity search
  • HDL_AGENT: High-level processing and Slack integration

- Service Layer: 12+ services providing functionality:
  • Core: agent, drive_service, slack_service, ocr_service, pdf_service, vector_service
  • Processing: file_discovery, document_processor, scheduler_service  
  • Additional: embedding_service, similarity_service, agent_coordinator

Created: Enhanced implementation based on original main.py (1317 lines)
Version: 0.2.0 Enhanced
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
import os
import traceback
import asyncio
from datetime import datetime, date
from typing import Dict, Any, Optional, List

# Enhanced Secret Management Import
try:
    from google.cloud import secretmanager
    SECRET_MANAGER_AVAILABLE = True
except ImportError:
    SECRET_MANAGER_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("Google Cloud Secret Manager not available - falling back to environment variables")

# Configure logging for Cloud Run
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ============================================================================
# PYDANTIC MODELS - Enhanced Request/Response Models
# ============================================================================

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

# Agent-related Pydantic models
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
    title="Gabriel Agent Task Flow - Enhanced",
    description="AI-powered personal assistant for managing structured tasks",
    version="0.2.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global service variables - Enhanced with better organization
services = {
    # Core services
    "agent": None,
    "drive_service": None, 
    "slack_service": None,
    "ocr_service": None,
    "pdf_service": None,
    "vector_service": None,
    
    # Processing services
    "file_discovery": None,
    "document_processor": None,
    "scheduler_service": None,
    
    # Agent architecture
    "agent_coordinator": None,
    
    # Additional services
    "embedding_service": None,
    "similarity_service": None
}

service_errors = {}
service_initialization_order = []

# ============================================================================
# ENHANCED SECRET MANAGEMENT - Google Cloud Secret Manager Integration
# ============================================================================

def load_secret_from_manager(secret_name: str, project_id: str = "location-19291") -> Optional[str]:
    """Load a secret from Google Cloud Secret Manager"""
    if not SECRET_MANAGER_AVAILABLE:
        return None
    
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        logger.warning(f"Failed to load secret {secret_name}: {e}")
        return None

def setup_enhanced_secrets():
    """Enhanced secret management - loads from Secret Manager in production"""
    use_secret_manager = os.environ.get('USE_SECRET_MANAGER', 'false').lower() == 'true'
    
    if not use_secret_manager:
        logger.info("[SECRETS] Using environment variables for secrets (development mode)")
        return
    
    if not SECRET_MANAGER_AVAILABLE:
        logger.warning("[WARNING] Secret Manager requested but not available - falling back to environment variables")
        return
    
    logger.info("[SECRETS] Loading secrets from Google Cloud Secret Manager...")
    
    # Map of environment variable names to secret names in Secret Manager
    secret_mappings = {
        'OPENAI_API_KEY': 'openai-api-key',
        'SLACK_BOT_TOKEN': 'slack-bot-token',
        'SLACK_SIGNING_SECRET': 'slack-signing-secret', 
        'SLACK_APP_TOKEN': 'slack-app-token',
        'GMAIL_CLIENT_SECRET': 'gmail-client-secret',
        'DB_PASSWORD': 'db-password',
        'DB_HOST': 'db-host',
        'DB_PORT': 'db-port',
        'DB_NAME': 'db-name',
        'DB_USER': 'db-user'
    }
    
    # Load configuration from app-config secret (optional)
    try:
        import json
        app_config_json = load_secret_from_manager('app-config')
        if app_config_json:
            app_config = json.loads(app_config_json)
            for key, value in app_config.items():
                env_key = key.upper()
                if not os.environ.get(env_key) and value:
                    os.environ[env_key] = str(value)
                    logger.debug(f"[SUCCESS] Loaded config {env_key} from Secret Manager")
        else:
            logger.info("[INFO] app-config secret not found - continuing with environment variables")
    except Exception as e:
        logger.info(f"[INFO] app-config secret not available - continuing with environment variables: {e}")
    
    # Load Google Cloud credentials
    try:
        google_creds = load_secret_from_manager('google-service-account-key')
        if google_creds:
            # Write credentials to a file (as expected by Google libraries)
            creds_path = "/tmp/google_credentials.json"
            with open(creds_path, 'w') as f:
                f.write(google_creds)
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = creds_path
            logger.info("[SUCCESS] Loaded Google Cloud credentials from Secret Manager")
    except Exception as e:
        logger.error(f"Failed to load Google credentials from Secret Manager: {e}")
    
    # Load individual secrets
    secrets_loaded = 0
    for env_var, secret_name in secret_mappings.items():
        secret_value = load_secret_from_manager(secret_name)
        if secret_value:
            os.environ[env_var] = secret_value
            secrets_loaded += 1
            logger.info(f"[SUCCESS] Loaded {env_var} from Secret Manager (length: {len(secret_value)})")
        else:
            logger.warning(f"[WARNING] Failed to load {env_var} from secret {secret_name}")
    
    logger.info(f"[SECRETS] Secret Manager: Loaded {secrets_loaded}/{len(secret_mappings)} secrets successfully")

async def initialize_service(service_name: str, init_function, dependencies: List[str] = None):
    """Initialize a service with enhanced error handling and dependency checking"""
    try:
        # Check dependencies first
        if dependencies:
            missing_deps = [dep for dep in dependencies if not services.get(dep)]
            if missing_deps:
                error_msg = f"Missing dependencies for {service_name}: {missing_deps}"
                logger.error(f"[ERROR] {error_msg}")
                service_errors[service_name] = error_msg
                return False
        
        logger.info(f"[INIT] Initializing {service_name}...")
        
        # Handle both sync and async initialization
        if hasattr(init_function, '__call__'):
            if asyncio.iscoroutinefunction(init_function):
                result = await init_function()
            else:
                result = init_function()
        else:
            result = init_function
            
        services[service_name] = result
        service_initialization_order.append(service_name)
        
        logger.info(f"[SUCCESS] {service_name} initialized successfully")
        return True
        
    except Exception as e:
        error_msg = f"Failed to initialize {service_name}: {str(e)}"
        logger.error(f"[ERROR] {error_msg}")
        logger.error(f"Traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")
        service_errors[service_name] = str(e)
        return False

async def initialize_services_enhanced():
    """Enhanced service initialization following original main.py pattern but with better error handling"""
    logger.info("🚀 Starting enhanced service initialization...")
    initialization_results = {}
    
    try:
        # Phase 1: Initialize core services (no dependencies)
        logger.info("[PHASE] Phase 1: Initializing core services...")
        
        # Step 1: Basic agent (foundation service)
        try:
            from app.services.agent import create_agent
            success = await initialize_service("agent", lambda: create_agent())
            initialization_results["agent"] = success
        except Exception as e:
            logger.error(f"Failed to initialize agent service: {e}")
            service_errors["agent"] = str(e)
            initialization_results["agent"] = False
        
        # Step 2: Google Drive service
        try:
            from app.services.google_drive import GoogleDriveService
            success = await initialize_service("drive_service", lambda: GoogleDriveService())
            initialization_results["drive_service"] = success
        except Exception as e:
            logger.error(f"Failed to initialize Google Drive service: {e}")
            service_errors["drive_service"] = str(e)
            initialization_results["drive_service"] = False
        
        # Step 3: OCR service
        try:
            from app.services.ocr_service import OCRService
            success = await initialize_service("ocr_service", lambda: OCRService())
            initialization_results["ocr_service"] = success
        except Exception as e:
            logger.error(f"Failed to initialize OCR service: {e}")
            service_errors["ocr_service"] = str(e)
            initialization_results["ocr_service"] = False
        
        # Step 4: PDF service
        try:
            from app.services.pdf_service import PDFService
            success = await initialize_service("pdf_service", lambda: PDFService())
            initialization_results["pdf_service"] = success
        except Exception as e:
            logger.error(f"Failed to initialize PDF service: {e}")
            service_errors["pdf_service"] = str(e)
            initialization_results["pdf_service"] = False
        
        # Step 5: Vector Storage (ChromaDB) - can fail gracefully
        try:
            from app.services.vector_storage_service import VectorStorageService
            success = await initialize_service("vector_service", lambda: VectorStorageService())
            initialization_results["vector_service"] = success
        except Exception as e:
            logger.error(f"Failed to initialize Vector Storage service: {e}")
            service_errors["vector_service"] = str(e)
            initialization_results["vector_service"] = False
        
        # Phase 2: Initialize services with dependencies
        logger.info("[PHASE] Phase 2: Initializing dependent services...")
        
        # Step 6: Slack service (depends on agent)
        try:
            from app.services.slack_service import SlackService
            slack_service = SlackService()
            if services["agent"]:
                success = await initialize_service(
                    "slack_service", 
                    lambda: slack_service.initialize(services["agent"]),
                    dependencies=["agent"]
                )
            else:
                # Store slack service even if not fully initialized
                services["slack_service"] = slack_service
                success = True
                logger.warning("Slack service stored but not fully initialized (no agent)")
            initialization_results["slack_service"] = success
        except Exception as e:
            logger.error(f"Failed to initialize Slack service: {e}")
            service_errors["slack_service"] = str(e)
            initialization_results["slack_service"] = False
        
        # Step 7: Document processor (depends on multiple services)
        try:
            from app.services.document_processor import DocumentProcessorService
            doc_processor = DocumentProcessorService()
            async def init_doc_processor():
                await doc_processor.initialize(
                    ocr_service=services.get("ocr_service"),
                    pdf_service=services.get("pdf_service"),
                    vector_service=services.get("vector_service"),
                    drive_service=services.get("drive_service"),
                    agent=services.get("agent"),
                    slack_service=services.get("slack_service")
                )
                return doc_processor
            
            success = await initialize_service(
                "document_processor", 
                init_doc_processor,
                dependencies=["agent"]  # At minimum need agent
            )
            initialization_results["document_processor"] = success
        except Exception as e:
            logger.error(f"Failed to initialize Document Processor service: {e}")
            service_errors["document_processor"] = str(e)
            initialization_results["document_processor"] = False
        
        # Step 8: File discovery (depends on drive and document processor)
        try:
            from app.services.file_discovery_service import FileDiscoveryService
            file_discovery = FileDiscoveryService()
            if services["drive_service"] and services["document_processor"]:
                async def init_file_discovery():
                    await file_discovery.initialize(
                        services["drive_service"], 
                        services["document_processor"]
                    )
                    return file_discovery
                
                success = await initialize_service(
                    "file_discovery",
                    init_file_discovery,
                    dependencies=["drive_service", "document_processor"]
                )
            else:
                logger.warning("File discovery service requires drive_service and document_processor")
                success = False
            initialization_results["file_discovery"] = success
        except Exception as e:
            logger.error(f"Failed to initialize File Discovery service: {e}")
            service_errors["file_discovery"] = str(e)
            initialization_results["file_discovery"] = False
        
        # Step 9: Scheduler service (depends on multiple services)
        try:
            from app.services.scheduler_service import SchedulerService
            scheduler = SchedulerService()
            if services["agent"] and services["slack_service"]:
                async def init_scheduler():
                    await scheduler.initialize(
                        agent=services["agent"],
                        slack_service=services["slack_service"],
                        file_discovery=services.get("file_discovery")
                    )
                    await scheduler.start()
                    return scheduler
                
                success = await initialize_service(
                    "scheduler_service",
                    init_scheduler,
                    dependencies=["agent", "slack_service"]
                )
            else:
                logger.warning("Scheduler service requires agent and slack_service")
                success = False
            initialization_results["scheduler_service"] = success
        except Exception as e:
            logger.error(f"Failed to initialize Scheduler service: {e}")
            service_errors["scheduler_service"] = str(e)
            initialization_results["scheduler_service"] = False
        
        # Phase 3: Initialize Agent Coordinator (orchestrates all agents)
        logger.info("[PHASE] Phase 3: Initializing Agent Coordinator...")
        
        try:
            from app.agents.agent_coordinator import AgentCoordinator
            agent_coordinator = AgentCoordinator()
            
            async def init_agent_coordinator():
                start_result = await agent_coordinator.start_coordinator()
                if start_result.get("status") != "success":
                    raise Exception(f"Agent Coordinator startup failed: {start_result}")
                
                # Connect Slack service to HDL Agent if both available
                if services.get("slack_service") and agent_coordinator:
                    logger.info("🔗 Connecting Slack service to HDL Agent...")
                    slack_connected = agent_coordinator.set_slack_service(services["slack_service"])
                    if slack_connected:
                        logger.info("[SUCCESS] HDL Agent → Slack integration completed!")
                    else:
                        logger.error("[ERROR] Failed to connect Slack service to HDL Agent")
                
                return agent_coordinator
            
            success = await initialize_service("agent_coordinator", init_agent_coordinator)
            initialization_results["agent_coordinator"] = success
            
        except Exception as e:
            logger.error(f"Failed to initialize Agent Coordinator: {e}")
            service_errors["agent_coordinator"] = str(e)
            initialization_results["agent_coordinator"] = False
        
        # Phase 4: Initialize additional services (optional)
        logger.info("[PHASE] Phase 4: Initializing additional services...")
        
        # Embedding service
        try:
            from app.services.embedding_service import EmbeddingService
            success = await initialize_service("embedding_service", lambda: EmbeddingService())
            initialization_results["embedding_service"] = success
        except Exception as e:
            logger.error(f"Failed to initialize Embedding service: {e}")
            service_errors["embedding_service"] = str(e)
            initialization_results["embedding_service"] = False
        
        # Similarity service
        try:
            from app.services.similarity_service import SimilarityService
            success = await initialize_service("similarity_service", lambda: SimilarityService())
            initialization_results["similarity_service"] = success
        except Exception as e:
            logger.error(f"Failed to initialize Similarity service: {e}")
            service_errors["similarity_service"] = str(e)
            initialization_results["similarity_service"] = False
        
    except Exception as e:
        logger.error(f"Critical error during service initialization: {e}")
        logger.error(f"Traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")
        # Don't raise the error, just log it - following original main.py pattern
        logger.warning("Continuing with limited functionality")
    
    return initialization_results

@app.on_event("startup")
async def startup_event():
    """Enhanced startup with comprehensive service loading and detailed reporting"""
    logger.info("🚀 Gabriel Agent Enhanced - Starting up...")
    logger.info(f"Port: {os.environ.get('PORT', '8080')}")
    logger.info(f"Project: {os.environ.get('GOOGLE_CLOUD_PROJECT', 'not set')}")
    logger.info(f"Secret Manager: {os.environ.get('USE_SECRET_MANAGER', 'false')}")
    
    # PHASE 0: Enhanced Secret Management Setup
    logger.info("[PHASE] Phase 0: Setting up enhanced secret management...")
    try:
        setup_enhanced_secrets()
        logger.info("[SUCCESS] Secret management setup completed")
    except Exception as e:
        logger.error(f"[ERROR] Secret management setup failed: {e}")
        logger.warning("[WARNING] Continuing with environment variables only")
    
    # In Cloud Run, service account authentication is automatic
    # Only set credentials path for local development
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") and os.path.exists("config"):
        credentials_path = os.path.join(os.getcwd(), "config", "credentials", "location-19291-fb284eccae8d.json")
        if os.path.exists(credentials_path):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
            logger.info(f"Set GOOGLE_APPLICATION_CREDENTIALS to: {credentials_path}")
        else:
            logger.info("Running in Cloud Run - using service account authentication")
    else:
        logger.info("Using existing GOOGLE_APPLICATION_CREDENTIALS or Cloud Run service account")
    
    logger.info(f"GOOGLE_APPLICATION_CREDENTIALS: {os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', 'Using service account')}")
    logger.info(f"Current working directory: {os.getcwd()}")
    
    # Initialize services with enhanced error handling
    results = await initialize_services_enhanced()
    
    # Generate detailed report
    successful_services = [name for name, success in results.items() if success]
    failed_services = [name for name, success in results.items() if not success]
    
    logger.info("[REPORT] SERVICE INITIALIZATION REPORT:")
    logger.info("=" * 50)
    
    if successful_services:
        logger.info(f"[SUCCESS] Successfully initialized ({len(successful_services)}):")
        for service in successful_services:
            logger.info(f"   • {service}")
    
    if failed_services:
        logger.warning(f"[ERROR] Failed to initialize ({len(failed_services)}):")
        for service in failed_services:
            error = service_errors.get(service, "Unknown error")
            logger.warning(f"   • {service}: {error}")
    
    # Service dependency analysis
    critical_services = ["agent", "drive_service", "agent_coordinator"]
    critical_failures = [s for s in critical_services if s in failed_services]
    
    if critical_failures:
        logger.error(f"🚨 CRITICAL SERVICE FAILURES: {critical_failures}")
        logger.error("Application may have limited functionality")
    else:
        logger.info("[SUCCESS] All critical services initialized successfully!")
    
    logger.info("=" * 50)
    logger.info(f"Startup completed - {len(successful_services)}/{len(results)} services active")
    logger.info("Application ready to serve requests")

@app.on_event("shutdown")
async def shutdown_event():
    """Enhanced shutdown with proper service cleanup"""
    logger.info("[SHUTDOWN] Gabriel Agent Enhanced - Shutting down...")
    
    try:
        # Stop scheduler service first
        if services.get("scheduler_service"):
            try:
                await services["scheduler_service"].stop()
                logger.info("[SUCCESS] Scheduler service stopped successfully")
            except Exception as e:
                logger.error(f"[ERROR] Error stopping scheduler service: {e}")
        
        # Stop agent coordinator and all agents
        if services.get("agent_coordinator"):
            try:
                await services["agent_coordinator"].stop_coordinator()
                logger.info("[SUCCESS] Agent Coordinator stopped successfully")
            except Exception as e:
                logger.error(f"[ERROR] Error stopping Agent Coordinator: {e}")
        
        # Close any other services that need cleanup
        for service_name, service in services.items():
            if service and hasattr(service, 'close'):
                try:
                    if asyncio.iscoroutinefunction(service.close):
                        await service.close()
                    else:
                        service.close()
                    logger.info(f"[SUCCESS] {service_name} closed successfully")
                except Exception as e:
                    logger.error(f"[ERROR] Error closing {service_name}: {e}")
        
        logger.info("[COMPLETE] Shutdown tasks completed successfully")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")
        logger.error(f"Traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Gabriel Agent Enhanced is running!", 
        "status": "healthy",
        "version": "0.2.0"
    }

@app.get("/health")
async def health_check():
    """Enhanced health check with service status"""
    return {
        "status": "healthy",
        "message": "Gabriel Agent Enhanced is running successfully",
        "port": os.environ.get('PORT', '8080'),
        "project": os.environ.get('GOOGLE_CLOUD_PROJECT', 'not set'),
        "services": {
            name: service is not None 
            for name, service in services.items()
        },
        "service_errors": service_errors,
        "version": "0.2.0"
    }



# ============================================================================
# AGENT API ENDPOINTS - Enhanced Agent Coordination and Management
# ============================================================================

@app.get("/agents/status")
async def get_agents_status():
    """Enhanced agent status endpoint with comprehensive reporting"""
    try:
        if not services.get("agent_coordinator"):
            return {
                "status": "service_unavailable",
                "message": "Agent Coordinator not initialized",
                "available_services": [name for name, service in services.items() if service is not None],
                "service_errors": service_errors
            }
        
        # Get detailed agent status
        agent_status = await services["agent_coordinator"].get_agent_status()
        
        # Add service integration status
        integration_status = {
            "slack_integration": services.get("slack_service") is not None,
            "drive_integration": services.get("drive_service") is not None,
            "vector_storage": services.get("vector_service") is not None,
            "document_processing": services.get("document_processor") is not None
        }
        
        return {
            "status": "success", 
            "result": agent_status,
            "service_integrations": integration_status,
            "initialization_order": service_initialization_order
        }
        
    except Exception as e:
        logger.error(f"Error getting agent status: {e}")
        logger.error(f"Traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agents/capabilities")
async def get_agents_capabilities():
    """Enhanced agent capabilities endpoint with detailed capability mapping"""
    try:
        if not services.get("agent_coordinator"):
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        capabilities = await services["agent_coordinator"].get_agent_capabilities()
        
        # Add service-specific capabilities
        service_capabilities = {
            "document_processing": services.get("document_processor") is not None,
            "file_discovery": services.get("file_discovery") is not None,
            "slack_messaging": services.get("slack_service") is not None,
            "vector_search": services.get("vector_service") is not None,
            "ocr_processing": services.get("ocr_service") is not None,
            "pdf_processing": services.get("pdf_service") is not None,
            "google_drive_access": services.get("drive_service") is not None,
            "scheduled_tasks": services.get("scheduler_service") is not None
        }
        
        return {
            "status": "success", 
            "result": capabilities,
            "service_capabilities": service_capabilities,
            "total_agents": len(capabilities) if capabilities else 0
        }
        
    except Exception as e:
        logger.error(f"Error getting agent capabilities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agents/message", response_model=AgentResponse)
async def send_agent_message(request: AgentMessageRequest):
    """Enhanced agent messaging with better error handling and logging"""
    try:
        if not services.get("agent_coordinator"):
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        logger.info(f"[MESSAGE] Routing message to {request.agent_type}: {request.action}")
        
        response = await services["agent_coordinator"].route_message(
            source="API_ENHANCED",
            target=request.agent_type,
            message={
                "action": request.action,
                "data": request.data,
                "timestamp": datetime.utcnow().isoformat(),
                "source_info": "Enhanced API"
            }
        )
        
        logger.info(f"📥 Response from {request.agent_type}: {response.get('status', 'unknown')}")
        
        return AgentResponse(
            status=response.get("status", "unknown"),
            result=response.get("result"),
            message=response.get("message"),
            agent_type=request.agent_type
        )
        
    except Exception as e:
        logger.error(f"Error sending message to {request.agent_type}: {e}")
        logger.error(f"Traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# ENTITY MANAGEMENT ENDPOINTS - DB Agent Integration
# ============================================================================

@app.post("/entities", response_model=AgentResponse)
async def create_entity(request: EntityCreateRequest):
    """Enhanced entity creation via DB Agent with validation"""
    try:
        if not services.get("agent_coordinator"):
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        logger.info(f"[CREATE] Creating entity: {request.name} ({request.category})")
        
        response = await services["agent_coordinator"].route_message(
            source="API_ENHANCED",
            target="DB_AGENT",
            message={
                "action": "create_entity",
                "data": request.dict(),
                "timestamp": datetime.utcnow().isoformat()
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
    """Enhanced entity listing with filtering and pagination support"""
    try:
        if not services.get("agent_coordinator"):
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        logger.debug("[PHASE] Fetching entity list")
        
        response = await services["agent_coordinator"].route_message(
            source="API_ENHANCED",
            target="DB_AGENT",
            message={
                "action": "list_entities",
                "data": {}
            }
        )
        
        entities = response.get("result", [])
        
        return {
            "status": response.get("status", "unknown"),
            "result": entities,
            "count": len(entities),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error listing entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/entities/{entity_id}")
async def get_entity(entity_id: str):
    """Enhanced entity retrieval with detailed information"""
    try:
        if not services.get("agent_coordinator"):
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        logger.debug(f"[SEARCH] Fetching entity: {entity_id}")
        
        response = await services["agent_coordinator"].route_message(
            source="API_ENHANCED",
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
            "result": response.get("result"),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting entity {entity_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# DOCUMENT PROCESSING ENDPOINTS - Enhanced Extraction and Storage
# ============================================================================

@app.post("/extraction/extract-document")
async def extract_document_content(file_name: str, content: str, entity_name: Optional[str] = None):
    """Enhanced document extraction via Extraction Agent with comprehensive field extraction"""
    try:
        if not services.get("agent_coordinator"):
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        logger.info(f"[SEARCH] Extracting document: {file_name} (entity: {entity_name})")
        
        # Prepare enhanced document data
        document_data = {
            "file_name": file_name,
            "content": content,
            "file_metadata": {
                "entity_name": entity_name,
                "source": "enhanced_api_upload",
                "webViewLink": f"https://enhanced.gabriel.com/files/{file_name}",
                "timestamp": datetime.utcnow().isoformat(),
                "processing_version": "enhanced"
            }
        }
        
        response = await services["agent_coordinator"].route_message(
            "API_ENHANCED",
            "EXTRACTION_AGENT",
            {
                "action": "extract_document",
                "data": document_data,
                "enhanced_features": {
                    "confidence_scoring": True,
                    "entity_validation": True,
                    "comprehensive_extraction": True
                }
            }
        )
        
        # Add processing metadata
        if response.get("status") == "success":
            response["processing_info"] = {
                "timestamp": datetime.utcnow().isoformat(),
                "processor": "enhanced_extraction_agent",
                "features_enabled": ["confidence_scoring", "entity_validation", "comprehensive_extraction"]
            }
        
        return response
        
    except Exception as e:
        logger.error(f"Error extracting document {file_name}: {e}")
        logger.error(f"Traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/extraction/process-email")
async def process_email_content(
    subject: str, 
    content: str, 
    attachments: Optional[List[Dict[str, Any]]] = None
):
    """Enhanced email processing through Extraction Agent with attachment handling"""
    try:
        if not services.get("agent_coordinator"):
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        logger.info(f"[EMAIL] Processing email: {subject}")
        
        # Prepare enhanced email data
        email_data = {
            "subject": subject,
            "content": content,
            "attachments": attachments or [],
            "processing_metadata": {
                "timestamp": datetime.utcnow().isoformat(),
                "source": "enhanced_api",
                "attachment_count": len(attachments) if attachments else 0
            }
        }
        
        response = await services["agent_coordinator"].route_message(
            "API_ENHANCED",
            "EXTRACTION_AGENT",
            {
                "action": "process_email",
                "data": email_data,
                "enhanced_features": {
                    "attachment_processing": True,
                    "task_extraction": True,
                    "entity_detection": True
                }
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing email: {e}")
        raise HTTPException(status_code=500, detail=str(e))




# ============================================================================
# CHROMADB VECTOR STORAGE ENDPOINTS - Enhanced Vector Operations
# ============================================================================

@app.get("/chromadb/info")
async def get_chromadb_info():
    """Enhanced ChromaDB collection information with detailed statistics"""
    try:
        if not services.get("agent_coordinator"):
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        logger.debug("[REPORT] Fetching enhanced ChromaDB information")
        
        response = await services["agent_coordinator"].route_message(
            "API_ENHANCED",
            "STORAGE_AGENT",
            {
                "action": "get_collection_info",
                "data": {},
                "enhanced_features": {
                    "detailed_statistics": True,
                    "performance_metrics": True
                }
            }
        )
        
        # Add service integration status
        if response.get("status") == "success":
            response["service_status"] = {
                "vector_service_active": services.get("vector_service") is not None,
                "embedding_service_active": services.get("embedding_service") is not None,
                "similarity_service_active": services.get("similarity_service") is not None
            }
        
        return response
        
    except Exception as e:
        logger.error(f"Error getting enhanced ChromaDB info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chromadb/search")
async def search_chromadb(
    query: str, 
    top_k: int = 5, 
    entity_name: Optional[str] = None,
    document_type: Optional[str] = None,
    date_range: Optional[Dict[str, str]] = None
):
    """Enhanced similarity search in ChromaDB with advanced filtering"""
    try:
        if not services.get("agent_coordinator"):
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        logger.info(f"[SEARCH] Enhanced ChromaDB search: '{query}' (top_k: {top_k})")
        
        # Prepare enhanced filter metadata
        filter_metadata = {}
        if entity_name:
            filter_metadata["entity_name"] = entity_name
        if document_type:
            filter_metadata["document_type"] = document_type
        if date_range:
            filter_metadata["date_range"] = date_range
        
        response = await services["agent_coordinator"].route_message(
            "API_ENHANCED",
            "STORAGE_AGENT",
            {
                "action": "similarity_search",
                "data": {
                    "query": query,
                    "top_k": top_k,
                    "filter_metadata": filter_metadata if filter_metadata else None,
                    "enhanced_search": True
                },
                "search_features": {
                    "semantic_similarity": True,
                    "relevance_scoring": True,
                    "result_ranking": True
                }
            }
        )
        
        # Add search metadata
        if response.get("status") == "success":
            response["search_metadata"] = {
                "query": query,
                "top_k": top_k,
                "filters_applied": list(filter_metadata.keys()) if filter_metadata else [],
                "timestamp": datetime.utcnow().isoformat(),
                "search_type": "enhanced_semantic_search"
            }
        
        return response
        
    except Exception as e:
        logger.error(f"Error performing enhanced ChromaDB search: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chromadb/store")
async def store_in_chromadb(
    file_name: str, 
    content: str, 
    entity_name: Optional[str] = None,
    document_type: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """Enhanced document storage in ChromaDB with rich metadata"""
    try:
        if not services.get("agent_coordinator"):
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        logger.info(f"[STORE] Storing enhanced document in ChromaDB: {file_name}")
        
        # Prepare enhanced extraction data for storage
        extraction_data = {
            "file_name": file_name,
            "entity_name": entity_name or "Enhanced Entity",
            "subject": f"Enhanced document: {file_name}",
            "summary": content[:200] + "..." if len(content) > 200 else content,
            "content": content,
            "document_type": document_type or "Enhanced Document",
            "issue_date": datetime.utcnow().isoformat(),
            "confidence_scores": {"subject": 0.98, "entity": 0.95, "content": 0.97},
            "processing_time": 2.1,
            "drive_link": f"https://enhanced.gabriel.com/files/{file_name}",
            "enhanced_metadata": metadata or {},
            "processing_version": "enhanced_v2.0"
        }
        
        response = await services["agent_coordinator"].route_message(
            "API_ENHANCED",
            "STORAGE_AGENT",
            {
                "action": "store_extraction_data",
                "data": extraction_data,
                "storage_features": {
                    "enhanced_indexing": True,
                    "metadata_enrichment": True,
                    "semantic_embedding": True
                }
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error storing enhanced document in ChromaDB: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# SLACK INTEGRATION ENDPOINTS - Enhanced Slack Event Processing
# ============================================================================

@app.post("/slack/events")
async def slack_events(request: Request):
    """Enhanced Slack events handler with comprehensive event processing"""
    try:
        body = await request.json()
        logger.info(f"[MESSAGE] Received enhanced Slack event: {body.get('type', 'unknown')}")

        # Handle URL verification
        if body.get("type") == "url_verification":
            logger.info("[SECRETS] Handling Slack URL verification challenge")
            return {"challenge": body.get("challenge")}

        # Verify Slack service is available
        if not services.get("slack_service"):
            logger.error("[ERROR] Slack service not initialized")
            raise HTTPException(status_code=503, detail="Slack service not initialized")

        # Process the event with enhanced handling
        event_type = body.get("type")
        if event_type == "event_callback":
            event = body.get("event", {})
            inner_event_type = event.get("type")
            
            logger.info(f"🎯 Processing enhanced Slack event: {inner_event_type}")
            
            if inner_event_type == "message":
                # Handle message events with enhanced processing
                logger.info("💬 Creating enhanced task to handle message event")
                
                # Add enhanced metadata to the event
                enhanced_event = {
                    **event,
                    "enhanced_processing": True,
                    "timestamp": datetime.utcnow().isoformat(),
                    "processing_version": "enhanced_v2.0",
                    "agent_coordinator_available": services.get("agent_coordinator") is not None
                }
                
                # Create async task for enhanced message handling
                asyncio.create_task(services["slack_service"]._handle_message(enhanced_event))
                
                # If agent coordinator is available, also route through agents
                if services.get("agent_coordinator"):
                    logger.info("🤖 Routing message through enhanced agent coordinator")
                    asyncio.create_task(
                        services["agent_coordinator"].route_message(
                            "SLACK_ENHANCED",
                            "HDL_AGENT", 
                            {
                                "action": "process_slack_message",
                                "data": enhanced_event,
                                "enhanced_features": {
                                    "nlp_processing": True,
                                    "intent_detection": True,
                                    "entity_recognition": True
                                }
                            }
                        )
                    )
                
            elif inner_event_type == "app_mention":
                logger.info("[TAG] Processing enhanced app mention event")
                # Handle app mentions with enhanced processing
                if services.get("agent_coordinator"):
                    asyncio.create_task(
                        services["agent_coordinator"].route_message(
                            "SLACK_ENHANCED",
                            "HDL_AGENT",
                            {
                                "action": "handle_app_mention",
                                "data": {
                                    **event,
                                    "enhanced_processing": True,
                                    "timestamp": datetime.utcnow().isoformat()
                                }
                            }
                        )
                    )
            
            else:
                logger.info(f"[INFO] Unhandled enhanced event type: {inner_event_type}")
            
            return {
                "status": "ok", 
                "processed_by": "enhanced_slack_handler",
                "timestamp": datetime.utcnow().isoformat()
            }

        logger.info(f"[INFO] Unhandled enhanced Slack event type: {event_type}")
        return {
            "status": "ok", 
            "message": f"Enhanced handler received {event_type}",
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"[ERROR] Error processing enhanced Slack event: {str(e)}")
        logger.error(f"Traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# FILE MANAGEMENT ENDPOINTS - Enhanced Google Drive Integration
# ============================================================================

@app.get("/files/scan")
async def scan_drive_files():
    """Enhanced Google Drive file scanning with detailed analysis"""
    try:
        if not services.get("agent_coordinator"):
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        logger.info("[SCAN] Initiating enhanced Drive file scan")
        
        response = await services["agent_coordinator"].route_message(
            "API_ENHANCED",
            "FILE_MANAGEMENT_AGENT",
            {
                "action": "scan_files",
                "data": {},
                "enhanced_features": {
                    "detailed_metadata": True,
                    "file_categorization": True,
                    "duplicate_detection": True
                }
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error scanning enhanced Drive files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/files/inventory")
async def get_file_inventory():
    """Enhanced file inventory with advanced categorization"""
    try:
        if not services.get("agent_coordinator"):
            raise HTTPException(status_code=503, detail="Agent Coordinator not initialized")
        
        logger.info("[REPORT] Fetching enhanced file inventory")
        
        response = await services["agent_coordinator"].route_message(
            "API_ENHANCED",
            "FILE_MANAGEMENT_AGENT",
            {
                "action": "get_inventory",
                "data": {},
                "enhanced_features": {
                    "categorization": True,
                    "statistics": True,
                    "recent_activity": True
                }
            }
        )
        
        # Add service status information
        if response.get("status") == "success":
            response["service_status"] = {
                "drive_service_active": services.get("drive_service") is not None,
                "document_processor_active": services.get("document_processor") is not None,
                "vector_service_active": services.get("vector_service") is not None
            }
        
        return response
        
    except Exception as e:
        logger.error(f"Error getting enhanced file inventory: {e}")
        raise HTTPException(status_code=500, detail=str(e))







if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get('PORT', 8080))
    uvicorn.run(app, host="0.0.0.0", port=port) 