ettindon;t se a starte#!/usr/bin/env python3
"""
Gabriel Agent - Minimal Cloud-Native Version
Simple, reliable startup for Google Cloud Run deployment
"""

import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure logging for Cloud Run
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Gabriel Agent - Cloud Native",
    description="AI-powered personal assistant - Minimal Cloud Deploy",
    version="1.0.0"
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
    """Root endpoint"""
    return {
        "message": "Gabriel Agent is running!",
        "status": "healthy",
        "version": "1.0.0",
        "environment": "cloud-native"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run"""
    return {
        "status": "healthy",
        "timestamp": "2025-09-10T01:40:00Z",
        "environment": {
            "port": os.environ.get("PORT", "8080"),
            "project": os.environ.get("GOOGLE_CLOUD_PROJECT", "unknown"),
            "use_secret_manager": os.environ.get("USE_SECRET_MANAGER", "false")
        }
    }

@app.get("/test")
async def test_endpoint():
    """Simple test endpoint"""
    try:
        return {
            "status": "success",
            "message": "Gabriel Agent test endpoint working",
            "project_id": os.environ.get("GOOGLE_CLOUD_PROJECT", "not-set"),
            "timestamp": "2025-09-10T01:40:00Z"
        }
    except Exception as e:
        logger.error(f"Test endpoint error: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)

