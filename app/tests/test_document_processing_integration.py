import asyncio
import logging
from datetime import datetime, timedelta
from ..services.agent import Agent
from ..services.document_processor import DocumentProcessorService
from ..services.google_drive import GoogleDriveService
from ..services.ocr_service import OCRService
from ..services.vector_storage_service import VectorStorageService
from ..services.slack_service import SlackService
from ..services.scheduler_service import SchedulerService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_document_processing_integration():
    """Test the complete document processing workflow including scheduler and vector database."""
    try:
        logger.info("Starting comprehensive document processing test")
        
        # Initialize all required services
        logger.info("Initializing services...")
        drive_service = GoogleDriveService()
        ocr_service = OCRService()
        vector_service = VectorStorageService()
        slack_service = SlackService()
        agent = Agent()
        
        # Initialize document processor with all services
        processor = DocumentProcessorService()
        await processor.initialize(
            ocr_service=ocr_service,
            vector_service=vector_service,
            drive_service=drive_service,
            agent=agent,
            slack_service=slack_service
        )
        
        # Initialize scheduler
        scheduler = SchedulerService()
        await scheduler.initialize(processor)
        
        # Test file ID from previous successful test
        test_file_id = "1i23QVF3CIbvG1XfhbpVOYhAW5V-WJwYz"
        
        # Step 1: Test direct document processing
        logger.info("Testing direct document processing...")
        result = await processor.process_document(test_file_id)
        
        if not result["success"]:
            raise Exception(f"Document processing failed: {result.get('error')}")
        
        logger.info("Direct document processing successful")
        
        # Step 2: Test vector database storage
        logger.info("Verifying vector database storage...")
        # Search for the document in vector database
        search_result = await vector_service.search_similar(
            query=result["document_info"]["entity_name"],
            top_k=1
        )
        
        if not search_result["success"] or not search_result["results"]:
            raise Exception("Document not found in vector database")
        
        logger.info("Vector database storage verified")
        
        # Step 3: Test scheduler
        logger.info("Testing scheduler...")
        
        # Schedule a document check
        check_time = datetime.utcnow() + timedelta(minutes=1)
        await scheduler.schedule_document_check(check_time)
        
        # Wait for scheduler to process
        logger.info("Waiting for scheduler to process...")
        await asyncio.sleep(70)  # Wait for 70 seconds to ensure processing
        
        # Verify scheduler processed the document
        scheduler_status = await scheduler.get_status()
        if not scheduler_status["last_check"]:
            raise Exception("Scheduler did not perform document check")
        
        logger.info("Scheduler test completed")
        
        # Step 4: Verify document was moved to correct folder
        logger.info("Verifying document location...")
        file_metadata = await drive_service.get_file_metadata(test_file_id)
        if not file_metadata.get("parents"):
            raise Exception("Document not moved to any folder")
        
        logger.info(f"Document moved to folder: {file_metadata['parents'][0]}")
        
        # Step 5: Clean up test data
        logger.info("Cleaning up test data...")
        try:
            # Remove document from vector database
            await vector_service.delete_document(test_file_id)
            logger.info("Test data cleaned up successfully")
        except Exception as e:
            logger.warning(f"Cleanup warning: {str(e)}")
        
        logger.info("Integration test completed successfully")
        return {
            "success": True,
            "message": "All integration tests passed",
            "document_info": result["document_info"],
            "vector_search": search_result,
            "scheduler_status": scheduler_status
        }
        
    except Exception as e:
        logger.error(f"Integration test failed: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

if __name__ == "__main__":
    asyncio.run(test_document_processing_integration()) 