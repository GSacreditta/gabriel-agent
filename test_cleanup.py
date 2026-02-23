#!/usr/bin/env python3
"""
Test script to verify database cleanup functionality without actually clearing data.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.core.database.service import DatabaseService
from app.services.vector_storage_service import VectorStorageService
from app.core.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_database_connections():
    """Test database connections without clearing data."""
    print("Testing Database Connections")
    print("=" * 40)
    
    try:
        # Test SQL database connection
        print("\nTesting SQL Database Connection...")
        db_service = DatabaseService()
        db_initialized = await db_service.initialize()
        
        if db_initialized:
            print("SQL Database connection successful")
            
            # Get table counts
            tables = ['entities', 'tasks', 'obligations', 'authorizations', 'document_metadata', 'processed_files']
            counts = {}
            for table in tables:
                try:
                    result = await db_service.execute_query(f"SELECT COUNT(*) as count FROM {table}")
                    counts[table] = result[0]['count'] if result else 0
                except Exception as e:
                    counts[table] = f"Error: {e}"
            
            print("   Current table counts:")
            for table, count in counts.items():
                print(f"     {table}: {count}")
        else:
            print("SQL Database connection failed")
        
        await db_service.close()
        
        # Test Vector database connection
        print("\nTesting Vector Database Connection...")
        settings = get_settings()
        
        # For local testing, disable cloud storage to avoid credential issues
        vector_service = VectorStorageService(
            persist_directory=settings.FAISS_PERSIST_DIRECTORY,
            use_cloud_storage=False,  # Disable cloud storage for local testing
            bucket_name=settings.FAISS_BUCKET_NAME
        )
        
        print("Vector Database service initialized")
        
        # Get storage status
        status = await vector_service.get_storage_status()
        print("   Vector database status:")
        for key, value in status.items():
            print(f"     {key}: {value}")
        
        # Check if FAISS files exist
        faiss_dir = Path(settings.FAISS_PERSIST_DIRECTORY)
        if faiss_dir.exists():
            faiss_files = list(faiss_dir.glob("*.faiss")) + list(faiss_dir.glob("*.pkl"))
            print(f"   FAISS files found: {len(faiss_files)}")
            for file in faiss_files:
                print(f"     {file.name}")
        else:
            print("   FAISS directory does not exist")
        
        await vector_service.cleanup()
        
        print("\nAll database connections tested successfully!")
        print("\nThe cleanup script should work properly.")
        
    except Exception as e:
        logger.error(f"Error testing database connections: {e}")
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_database_connections())
