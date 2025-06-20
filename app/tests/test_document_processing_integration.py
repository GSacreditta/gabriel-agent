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
from ..services.file_discovery_service import FileDiscoveryService
from ..tools.ocr_tool import OCRTool
from ..tools.drive_tool import DriveTool
from ..core.config import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_document_processing_integration():
    """Test the complete document processing workflow including scheduler and vector database."""
    try:
        logger.info("Starting comprehensive document processing test")
        
        # Get settings
        settings = get_settings()
        
        # Initialize tools and services
        logger.info("Initializing tools and services...")
        drive_service = GoogleDriveService()
        vector_service = VectorStorageService()
        slack_service = SlackService()
        
        # Initialize tools with services
        drive_tool = DriveTool()
        ocr_tool = OCRTool()
        agent = Agent()  # This will initialize with the tools
        
        # Initialize document processor with all services
        processor = DocumentProcessorService()
        await processor.initialize(
            ocr_service=ocr_tool._ocr_service,  # Use the OCR service from the tool
            vector_service=vector_service,
            drive_service=drive_service,
            agent=agent,
            slack_service=slack_service
        )
        
        # Initialize file discovery service
        file_discovery = FileDiscoveryService()
        await file_discovery.initialize(
            drive_service=drive_service,
            document_processor=processor
        )
        
        # Initialize scheduler
        scheduler = SchedulerService()
        await scheduler.initialize(
            agent=agent,
            slack_service=slack_service,
            file_discovery=file_discovery
        )
        
        # Step 1: Use FileDiscoveryService to find available documents
        logger.info("Finding available documents using FileDiscoveryService...")
        scan_result = await file_discovery.scan_folder()
        
        if not scan_result["success"]:
            raise Exception(f"Document scan failed: {scan_result.get('error')}")
            
        if scan_result["files_processed"] == 0:
            raise Exception("No documents found in the folder")
            
        # Get the first available document for testing
        test_file = scan_result.get("files", [])[0]
        test_file_id = test_file.get("id")
        logger.info(f"Found test file: {test_file.get('name')} (ID: {test_file_id})")
        
        # Step 2: Process document with OCR tool
        logger.info("Processing document with OCR...")
        ocr_result = await ocr_tool._arun(
            file_id=test_file_id,
            extract_structured=True
        )
        
        if not ocr_result.get("success"):
            raise Exception(f"OCR processing failed: {ocr_result.get('error')}")
        
        logger.info("OCR processing successful")
        
        # Step 3: Process document through processor
        logger.info("Processing document through processor...")
        result = await processor.process_document(test_file_id)
        
        if not result["success"]:
            raise Exception(f"Document processing failed: {result.get('error')}")
        
        logger.info("Document processing successful")
        
        # Step 4: Test vector database storage
        logger.info("Verifying vector database storage...")
        search_result = await vector_service.search_similar(
            query=result["document_info"]["entity_name"],
            top_k=1
        )
        
        if not search_result["success"] or not search_result["results"]:
            raise Exception("Document not found in vector database")
        
        logger.info("Vector database storage verified")
        
        # Step 5: Test scheduler
        logger.info("Testing scheduler...")
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
        
        # Step 6: Verify document was moved to correct folder
        logger.info("Verifying document location...")
        file_metadata = await drive_service.get_file_metadata(test_file_id)
        if not file_metadata.get("parents"):
            raise Exception("Document not moved to any folder")
        
        logger.info(f"Document moved to folder: {file_metadata['parents'][0]}")
        
        # Step 7: Clean up test data
        logger.info("Cleaning up test data...")
        try:
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
    # Run the test
    result = asyncio.run(test_document_processing_integration())
    if result["success"]:
        logger.info("All tests passed successfully!")
    else:
        logger.error(f"Tests failed: {result.get('error')}") 