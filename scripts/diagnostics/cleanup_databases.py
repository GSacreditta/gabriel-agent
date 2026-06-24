#!/usr/bin/env python3
"""
Database Cleanup Script
Clears all entries from both SQL database tables and FAISS vector database.
"""

import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import Dict, Any, List
import sys

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


class DatabaseCleanupService:
    """Service to clean up both SQL and Vector databases."""
    
    def __init__(self):
        self.settings = get_settings()
        self.db_service = None
        self.vector_service = None
        
    async def initialize(self) -> bool:
        """Initialize database connections."""
        try:
            # Initialize SQL database service
            self.db_service = DatabaseService()
            db_initialized = await self.db_service.initialize()
            
            if not db_initialized:
                logger.error("Failed to initialize SQL database service")
                return False
                
            # Initialize Vector database service
            # For cleanup, we'll handle cloud storage manually to avoid credential issues
            self.vector_service = VectorStorageService(
                persist_directory=self.settings.FAISS_PERSIST_DIRECTORY,
                use_cloud_storage=False,  # Disable cloud storage for local cleanup
                bucket_name=self.settings.FAISS_BUCKET_NAME
            )
            
            logger.info("✅ Database services initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize database services: {e}")
            return False
    
    async def get_sql_table_counts(self) -> Dict[str, int]:
        """Get current row counts for all SQL tables."""
        try:
            tables = [
                'entities', 'tasks', 'obligations', 'authorizations', 
                'document_metadata', 'processed_files'
            ]
            
            counts = {}
            for table in tables:
                try:
                    result = await self.db_service.execute_query(f"SELECT COUNT(*) as count FROM {table}")
                    counts[table] = result[0]['count'] if result else 0
                except Exception as e:
                    logger.warning(f"Could not get count for table {table}: {e}")
                    counts[table] = 0
                    
            return counts
        except Exception as e:
            logger.error(f"Error getting SQL table counts: {e}")
            return {}
    
    async def clear_sql_tables(self) -> Dict[str, Any]:
        """Clear all SQL database tables."""
        try:
            logger.info("🗑️  Starting SQL database cleanup...")
            
            # Get initial counts
            initial_counts = await self.get_sql_table_counts()
            logger.info(f"Initial SQL table counts: {initial_counts}")
            
            # Clear tables in reverse dependency order to avoid foreign key constraints
            tables_to_clear = [
                'processed_files',      # No dependencies
                'document_metadata',    # Depends on entities
                'authorizations',       # Depends on entities  
                'obligations',          # Depends on entities
                'tasks',                # Depends on entities
                'entities'              # Base table
            ]
            
            cleared_counts = {}
            
            for table in tables_to_clear:
                try:
                    # Use TRUNCATE CASCADE to handle foreign key constraints
                    result = await self.db_service.execute_command(f"TRUNCATE TABLE {table} CASCADE")
                    cleared_counts[table] = result
                    logger.info(f"✅ Cleared table '{table}': {result} rows affected")
                except Exception as e:
                    logger.error(f"❌ Failed to clear table '{table}': {e}")
                    cleared_counts[table] = f"Error: {e}"
            
            # Get final counts
            final_counts = await self.get_sql_table_counts()
            logger.info(f"Final SQL table counts: {final_counts}")
            
            return {
                "status": "success",
                "initial_counts": initial_counts,
                "final_counts": final_counts,
                "cleared_counts": cleared_counts
            }
            
        except Exception as e:
            logger.error(f"Error clearing SQL tables: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    async def clear_vector_database(self) -> Dict[str, Any]:
        """Clear FAISS vector database."""
        try:
            logger.info("🗑️  Starting Vector database cleanup...")
            
            # Get initial status
            initial_status = await self.vector_service.get_storage_status()
            logger.info(f"Initial vector database status: {initial_status}")
            
            # Clear local FAISS files
            faiss_dir = Path(self.settings.FAISS_PERSIST_DIRECTORY)
            cleared_files = []
            
            if faiss_dir.exists():
                # List files to be deleted
                faiss_files = list(faiss_dir.glob("*.faiss")) + list(faiss_dir.glob("*.pkl"))
                cleared_files = [str(f) for f in faiss_files]
                
                # Delete FAISS files
                for file_path in faiss_files:
                    try:
                        file_path.unlink()
                        logger.info(f"✅ Deleted vector file: {file_path.name}")
                    except Exception as e:
                        logger.warning(f"Could not delete {file_path.name}: {e}")
                
                # If directory is empty, remove it
                try:
                    if not any(faiss_dir.iterdir()):
                        faiss_dir.rmdir()
                        logger.info(f"✅ Removed empty directory: {faiss_dir}")
                except Exception as e:
                    logger.warning(f"Could not remove directory {faiss_dir}: {e}")
            else:
                logger.info("Vector database directory does not exist")
            
            # Clear cloud storage if enabled
            cloud_cleared = False
            if self.settings.FAISS_USE_CLOUD_STORAGE and hasattr(self.vector_service, 'bucket'):
                try:
                    # Delete cloud storage files
                    bucket = self.vector_service.bucket
                    blobs_to_delete = [
                        f"{self.vector_service.index_name}.faiss",
                        f"{self.vector_service.index_name}.pkl"
                    ]
                    
                    for blob_name in blobs_to_delete:
                        blob = bucket.blob(blob_name)
                        if blob.exists():
                            blob.delete()
                            logger.info(f"✅ Deleted cloud storage file: {blob_name}")
                    
                    cloud_cleared = True
                    logger.info("✅ Cloud storage cleared successfully")
                except Exception as e:
                    logger.warning(f"Could not clear cloud storage: {e}")
            
            # Reset vector service
            self.vector_service.vector_store = None
            
            # Get final status
            final_status = await self.vector_service.get_storage_status()
            logger.info(f"Final vector database status: {final_status}")
            
            return {
                "status": "success",
                "initial_status": initial_status,
                "final_status": final_status,
                "cleared_files": cleared_files,
                "cloud_cleared": cloud_cleared
            }
            
        except Exception as e:
            logger.error(f"Error clearing vector database: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    async def cleanup(self):
        """Cleanup resources."""
        try:
            if self.db_service:
                await self.db_service.close()
            if self.vector_service:
                await self.vector_service.cleanup()
            logger.info("✅ Cleanup completed")
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")


async def main():
    """Main cleanup function."""
    print("Gabriel Agent Database Cleanup Tool")
    print("=" * 50)
    
    # Confirm action
    print("\nWARNING: This will permanently delete ALL data from:")
    print("   - SQL Database (entities, tasks, obligations, authorizations, document_metadata, processed_files)")
    print("   - FAISS Vector Database (all document embeddings)")
    print("\nThis action cannot be undone!")
    
    response = input("\nAre you sure you want to proceed? (type 'YES' to confirm): ")
    if response != 'YES':
        print("Cleanup cancelled by user")
        return
    
    # Initialize cleanup service
    cleanup_service = DatabaseCleanupService()
    
    try:
        # Initialize services
        if not await cleanup_service.initialize():
            print("❌ Failed to initialize database services")
            return
        
        print("\n🚀 Starting database cleanup...")
        
        # Clear SQL tables
        print("\n📊 Clearing SQL Database...")
        sql_result = await cleanup_service.clear_sql_tables()
        
        if sql_result["status"] == "success":
            print("✅ SQL Database cleared successfully")
            print(f"   Initial counts: {sql_result['initial_counts']}")
            print(f"   Final counts: {sql_result['final_counts']}")
        else:
            print(f"❌ SQL Database cleanup failed: {sql_result['message']}")
        
        # Clear Vector database
        print("\n🔍 Clearing Vector Database...")
        vector_result = await cleanup_service.clear_vector_database()
        
        if vector_result["status"] == "success":
            print("✅ Vector Database cleared successfully")
            print(f"   Cleared files: {len(vector_result['cleared_files'])}")
            print(f"   Cloud storage cleared: {vector_result['cloud_cleared']}")
        else:
            print(f"❌ Vector Database cleanup failed: {vector_result['message']}")
        
        # Summary
        print("\n" + "=" * 50)
        print("🎉 CLEANUP COMPLETE!")
        print("=" * 50)
        
        if sql_result["status"] == "success" and vector_result["status"] == "success":
            print("✅ Both SQL and Vector databases have been successfully cleared")
        else:
            print("⚠️  Some cleanup operations may have failed - check logs above")
        
    except Exception as e:
        logger.error(f"Unexpected error during cleanup: {e}")
        print(f"❌ Unexpected error: {e}")
    
    finally:
        # Cleanup resources
        await cleanup_service.cleanup()


if __name__ == "__main__":
    # Run the cleanup
    asyncio.run(main())
