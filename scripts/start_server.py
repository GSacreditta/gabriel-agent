#!/usr/bin/env python3
"""
Gabriel Agent Production Server Startup Script

This script ensures proper module path setup and runs the FastAPI server
with all services correctly initialized for production deployment.

Usage:
    python start_server.py [--port 8080] [--host 0.0.0.0]
"""

import sys
import os
import argparse
from pathlib import Path

def setup_python_path():
    """Ensure the app directory is in Python path for proper module imports."""
    current_dir = Path(__file__).parent.absolute()
    app_path = current_dir / "app"
    
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))
    if str(app_path) not in sys.path:
        sys.path.insert(0, str(app_path))
    
    print(f"✅ Python path configured for Gabriel Agent")
    print(f"   Project root: {current_dir}")
    print(f"   App directory: {app_path}")

def main():
    """Main startup function."""
    parser = argparse.ArgumentParser(description="Gabriel Agent Production Server")
    parser.add_argument("--port", type=int, default=8080, help="Port to run the server on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    
    args = parser.parse_args()
    
    print("🚀 Gabriel Agent Production Server")
    print("=" * 50)
    
    # Setup Python path
    setup_python_path()
    
    # Import after path setup
    import uvicorn
    
    # Configure for production vs development
    uvicorn_config = {
        "app": "app.main:app",
        "host": args.host,
        "port": args.port,
        "reload": args.reload,
        "access_log": True,
        "log_level": "info"
    }
    
    # Production optimizations
    if not args.reload:
        uvicorn_config.update({
            "workers": 1,  # Single worker for now, can be increased
            "loop": "asyncio",
            "http": "httptools"
        })
    
    print(f"🌐 Starting server on {args.host}:{args.port}")
    print(f"📊 Mode: {'Development' if args.reload else 'Production'}")
    print("=" * 50)
    
    try:
        uvicorn.run(**uvicorn_config)
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Server failed to start: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
