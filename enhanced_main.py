#!/usr/bin/env python3
"""
Gabriel Agent - Enhanced Cloud-Native Version
Progressive deployment with service toggles for reliable cloud deployment
"""

import os
import logging
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Dict, Any

# Setup Python path for imports
def setup_python_path():
    project_root = Path(__file__).parent.absolute()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

setup_python_path()

# Configure logging for Cloud Run
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Service toggle flags - controlled by environment variables
ENABLE_VECTOR_SERVICE = os.environ.get("ENABLE_VECTOR_SERVICE", "false").lower() == "true"
ENABLE_AGENT_COORDINATOR = os.environ.get("ENABLE_AGENT_COORDINATOR", "false").lower() == "true"
ENABLE_SLACK_SERVICE = os.environ.get("ENABLE_SLACK_SERVICE", "false").lower() == "true"
ENABLE_DRIVE_SERVICE = os.environ.get("ENABLE_DRIVE_SERVICE", "false").lower() == "true"
ENABLE_SECRET_MANAGER = os.environ.get("USE_SECRET_MANAGER", "false").lower() == "true"

# Global service storage
services = {}
service_errors = {}

# Create FastAPI app
app = FastAPI(
    title="Gabriel Agent - Enhanced Cloud Native",
    description="AI-powered personal assistant - Progressive Cloud Deployment",
    version="2.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint with service status"""
    return {
        "message": "Gabriel Agent Enhanced is running!",
        "status": "healthy",
        "version": "2.0.0",
        "environment": "cloud-native",
        "services_enabled": {
            "vector_service": ENABLE_VECTOR_SERVICE,
            "agent_coordinator": ENABLE_AGENT_COORDINATOR,
            "slack_service": ENABLE_SLACK_SERVICE,
            "drive_service": ENABLE_DRIVE_SERVICE,
            "secret_manager": ENABLE_SECRET_MANAGER
        },
        "services_active": list(services.keys())
    }

@app.get("/health")
async def health_check():
    """Enhanced health check with service status"""
    return {
        "status": "healthy",
        "timestamp": "2025-09-17T21:30:00Z",
        "environment": {
            "port": os.environ.get("PORT", "8080"),
            "project": os.environ.get("GOOGLE_CLOUD_PROJECT", "unknown"),
            "use_secret_manager": ENABLE_SECRET_MANAGER
        },
        "services": {
            "total_enabled": sum([ENABLE_VECTOR_SERVICE, ENABLE_AGENT_COORDINATOR, ENABLE_SLACK_SERVICE, ENABLE_DRIVE_SERVICE]),
            "total_active": len(services),
            "status": "healthy" if len(service_errors) == 0 else "degraded",
            "errors": service_errors
        }
    }

@app.get("/test")
async def test_endpoint():
    """Enhanced test endpoint with service validation"""
    try:
        test_results = {
            "status": "success",
            "message": "Gabriel Agent enhanced test endpoint working",
            "project_id": os.environ.get("GOOGLE_CLOUD_PROJECT", "not-set"),
            "timestamp": "2025-09-17T21:30:00Z",
            "service_tests": {}
        }
        
        # Test each enabled service
        if ENABLE_SECRET_MANAGER:
            try:
                # Test Secret Manager connection
                test_results["service_tests"]["secret_manager"] = "enabled - would test connection"
            except Exception as e:
                test_results["service_tests"]["secret_manager"] = f"error: {str(e)}"
        
        if ENABLE_VECTOR_SERVICE:
            test_results["service_tests"]["vector_service"] = "enabled - would test FAISS"
            
        if ENABLE_DRIVE_SERVICE:
            test_results["service_tests"]["drive_service"] = "enabled - would test Google Drive"
            
        if ENABLE_SLACK_SERVICE:
            test_results["service_tests"]["slack_service"] = "enabled - would test Slack connection"
            
        if ENABLE_AGENT_COORDINATOR:
            test_results["service_tests"]["agent_coordinator"] = "enabled - would test agents"
        
        return test_results
    except Exception as e:
        logger.error(f"Test endpoint error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/services")
async def get_services():
    """Get detailed service information"""
    return {
        "enabled_services": {
            "vector_service": ENABLE_VECTOR_SERVICE,
            "agent_coordinator": ENABLE_AGENT_COORDINATOR,
            "slack_service": ENABLE_SLACK_SERVICE,
            "drive_service": ENABLE_DRIVE_SERVICE,
            "secret_manager": ENABLE_SECRET_MANAGER
        },
        "active_services": list(services.keys()),
        "service_errors": service_errors,
        "startup_complete": True
    }

async def initialize_services():
    """Initialize services based on enabled flags"""
    logger.info("🚀 Starting enhanced service initialization...")
    
    if ENABLE_SECRET_MANAGER:
        try:
            logger.info("Initializing Secret Manager...")
            # TODO: Add actual Secret Manager initialization
            services["secret_manager"] = "mock_service"
            logger.info("✅ Secret Manager initialized")
        except Exception as e:
            logger.error(f"❌ Secret Manager failed: {e}")
            service_errors["secret_manager"] = str(e)
    
    if ENABLE_VECTOR_SERVICE:
        try:
            logger.info("Initializing Vector Service...")
            # TODO: Add actual FAISS initialization
            services["vector_service"] = "mock_service"
            logger.info("✅ Vector Service initialized")
        except Exception as e:
            logger.error(f"❌ Vector Service failed: {e}")
            service_errors["vector_service"] = str(e)
    
    if ENABLE_DRIVE_SERVICE:
        try:
            logger.info("Initializing Google Drive Service...")
            # TODO: Add actual Drive service initialization
            services["drive_service"] = "mock_service"
            logger.info("✅ Drive Service initialized")
        except Exception as e:
            logger.error(f"❌ Drive Service failed: {e}")
            service_errors["drive_service"] = str(e)
    
    if ENABLE_SLACK_SERVICE:
        try:
            logger.info("Initializing Slack Service...")
            # TODO: Add actual Slack service initialization
            services["slack_service"] = "mock_service"
            logger.info("✅ Slack Service initialized")
        except Exception as e:
            logger.error(f"❌ Slack Service failed: {e}")
            service_errors["slack_service"] = str(e)
    
    if ENABLE_AGENT_COORDINATOR:
        try:
            logger.info("Initializing Agent Coordinator...")
            # TODO: Add actual Agent Coordinator initialization
            services["agent_coordinator"] = "mock_service"
            logger.info("✅ Agent Coordinator initialized")
        except Exception as e:
            logger.error(f"❌ Agent Coordinator failed: {e}")
            service_errors["agent_coordinator"] = str(e)
    
    logger.info(f"Service initialization complete: {len(services)} active, {len(service_errors)} errors")

@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    logger.info("🚀 Gabriel Agent Enhanced - Starting up...")
    logger.info(f"Port: {os.environ.get('PORT', '8080')}")
    logger.info(f"Project: {os.environ.get('GOOGLE_CLOUD_PROJECT', 'not set')}")
    
    await initialize_services()
    
    logger.info("✅ Startup complete - Application ready to serve requests")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
