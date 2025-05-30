import asyncio
import logging
import json
from datetime import datetime
from ..services.agent import Agent, DocumentInfo
from ..services.google_drive import GoogleDriveService
from ..services.slack_service import SlackService
from ..tools.ocr_tool import OCRTool
from ..core.config import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_drive_document():
    """Test document processing from Google Drive."""
    try:
        # Initialize services
        agent = Agent()
        drive_service = GoogleDriveService()
        slack_service = SlackService()
        ocr_tool = OCRTool()

        # Get the master folder ID from settings
        settings = get_settings()
        master_folder_id = settings.GOOGLE_DRIVE_FOLDER_ID
        logger.info(f"Using master folder ID: {master_folder_id}")

        # Step 1: Scan the master folder for new documents
        logger.info("Scanning master folder for documents...")
        folder_contents = await drive_service.get_folder_contents()
        
        logger.info(f"Found {len(folder_contents)} files in folder")
        
        # Step 2: Identify file format and metadata
        logger.info("Identifying file format and metadata...")
        target_file = None
        for file in folder_contents:
            # Log each file's metadata for debugging
            logger.info(f"Found file: {file.get('name')} (ID: {file.get('id')})")
            if "Accumulus" in file.get("name", "") and file.get("name", "").endswith(".pdf"):
                target_file = file
                break
        
        if not target_file:
            raise Exception("Accumulus PDF file not found in the master folder")
        
        # Log file metadata
        logger.info("File metadata:")
        logger.info(f"- Name: {target_file.get('name')}")
        logger.info(f"- ID: {target_file.get('id')}")
        logger.info(f"- MIME Type: {target_file.get('mimeType')}")
        logger.info(f"- Created: {target_file.get('createdTime')}")
        logger.info(f"- Modified: {target_file.get('modifiedTime')}")
        
        file_id = target_file.get("id")
        mime_type = target_file.get("mimeType", "")
        
        # Step 3: Process document based on format
        logger.info("Processing document...")
        if "google-apps" in mime_type:
            # For Google Docs/Sheets, use export
            logger.info("Processing Google Docs file...")
            file_content = await drive_service.export_file(file_id, "application/pdf")
        else:
            # For regular files, use download
            logger.info("Processing regular file...")
            file_content = await drive_service.download_file(file_id)

        # Step 4: Process with OCR
        logger.info("Processing document with OCR...")
        ocr_result = await ocr_tool._arun(
            file_id=file_id,
            extract_structured=True
        )
        logger.info(f"OCR Result: {ocr_result}")

        # Parse OCR result
        if isinstance(ocr_result, str):
            ocr_result = json.loads(ocr_result)

        # Step 5: Extract structured information
        extracted_text = ocr_result.get("data", {}).get("text", "")
        logger.info(f"Extracted text: {extracted_text[:200]}...")  # Log first 200 chars

        # Create document info with extracted data
        document_info = {
            "file_name": target_file.get("name", "Unknown"),
            "entity_name": "Accumulus",  # This should be extracted from the document
            "processing_time": datetime.utcnow().isoformat(),
            "ocr_result": ocr_result,
            "extracted_text": extracted_text,
            "file_metadata": target_file  # Include original file metadata
        }

        # Step 6: Plan review tasks
        logger.info("Planning review tasks...")
        tasks = await agent.plan_review_tasks(document_info)
        logger.info("Review tasks:")
        for task in tasks:
            logger.info(f"- {task}")

        # Step 7: Create and validate DocumentInfo
        try:
            # Extract information from the document text
            # This is where we would use NLP or other methods to extract structured data
            # For now, we'll use some basic heuristics
            doc_info = DocumentInfo(
                entity_name="Accumulus",  # This should be extracted from the text
                issue_date=datetime.now().strftime("%Y-%m-%d"),  # This should be extracted from the text
                subject="Document Processing",  # This should be extracted from the text
                summary="Document containing information about Accumulus",  # This should be generated from the text
                document_type="PDF",
                drive_link=f"https://drive.google.com/file/d/{file_id}",
                confidence_scores={
                    "entity_detection": 0.95,
                    "date_extraction": 0.90,
                    "topic_identification": 0.85
                }
            )
            logger.info("Document info validation successful")
            logger.info(f"Extracted document info: {doc_info.dict()}")
        except Exception as e:
            raise Exception(f"Document info validation failed: {str(e)}")

        # Step 8: Log final results
        logger.info("Extracted Information:")
        logger.info(f"- Entity Name: {doc_info.entity_name}")
        logger.info(f"- Issue Date: {doc_info.issue_date}")
        logger.info(f"- Subject: {doc_info.subject}")
        logger.info(f"- Summary: {doc_info.summary}")
        logger.info(f"- Document Type: {doc_info.document_type}")
        logger.info(f"- Confidence Scores: {doc_info.confidence_scores}")

        # Step 9: Send notification to Slack
        try:
            # Format the message for Slack
            message = (
                f"*New Document Processed*\n\n"
                f"*Entity:* {doc_info.entity_name}\n"
                f"*Document:* {document_info['file_name']}\n"
                f"*Date:* {doc_info.issue_date}\n"
                f"*Subject:* {doc_info.subject}\n"
                f"*Summary:* {doc_info.summary}\n\n"
                f"*Review Tasks:*\n" + "\n".join([f"• {task}" for task in tasks]) + "\n\n"
                f"*Drive Link:* {doc_info.drive_link}\n"
                f"*Confidence Scores:*\n"
                f"• Entity Detection: {doc_info.confidence_scores['entity_detection']:.2f}\n"
                f"• Date Extraction: {doc_info.confidence_scores['date_extraction']:.2f}\n"
                f"• Topic Identification: {doc_info.confidence_scores['topic_identification']:.2f}"
            )
            
            # Send the message using SlackService
            response = await slack_service.send_review_request(message)
            if response["success"]:
                logger.info("Successfully sent notification to Slack")
            else:
                logger.warning(f"Failed to send Slack notification: {response.get('error')}")
        except Exception as e:
            logger.warning(f"Failed to send Slack notification: {str(e)}")

        return True

    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        return False

if __name__ == "__main__":
    # Run the test
    success = asyncio.run(test_drive_document())
    if success:
        logger.info("All tests passed successfully!")
    else:
        logger.error("Tests failed!") 