import asyncio
import logging
import os
from pathlib import Path
import fitz  # PyMuPDF
from ..services.agent import Agent, DocumentInfo
from ..tools.ocr_tool import OCRTool
from ..tools.drive_tool import DriveTool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_document_processing():
    """Test document processing functionality."""
    try:
        # Initialize services
        agent = Agent()
        ocr_tool = OCRTool()
        drive_tool = DriveTool()

        # Get test document path
        test_doc_path = Path(__file__).parent.parent / "test_documents" / "Accumulus.pdf"
        if not test_doc_path.exists():
            raise FileNotFoundError(f"Test document not found at {test_doc_path}")

        # First try to extract text directly from PDF
        logger.info(f"Extracting text from PDF: {test_doc_path}")
        doc = fitz.open(test_doc_path)
        pdf_text = ""
        for page in doc:
            pdf_text += page.get_text()
        doc.close()

        if not pdf_text.strip():
            logger.info("No text found in PDF, falling back to OCR...")
            # If no text found, use OCR
            ocr_result = await ocr_tool._ocr_service._process_pdf(
                file_content=test_doc_path.read_bytes(),
                file_id=str(test_doc_path)
            )
            if not ocr_result["success"]:
                raise Exception(f"OCR processing failed: {ocr_result.get('error')}")
            extracted_text = ocr_result["text"]
        else:
            logger.info("Successfully extracted text directly from PDF")
            extracted_text = pdf_text

        # Create document info
        document_info = {
            "file_name": test_doc_path.name,
            "entity_name": "Accumulus",
            "processing_time": "2024-03-20T10:00:00Z",
            "ocr_result": {
                "success": True,
                "text": extracted_text,
                "file_id": str(test_doc_path)
            }
        }

        # Plan review tasks
        logger.info("Planning review tasks...")
        tasks = await agent.plan_review_tasks(document_info)
        logger.info("Review tasks:")
        for task in tasks:
            logger.info(f"- {task}")

        # Test document info validation
        try:
            doc_info = DocumentInfo(
                entity_name="Accumulus",
                issue_date="2024-03-20",
                subject="Test Document",
                summary="This is a test document for processing",
                document_type="PDF",
                drive_link="https://drive.google.com/test",
                confidence_scores={
                    "entity_detection": 0.95,
                    "date_extraction": 0.90,
                    "topic_identification": 0.85
                }
            )
            logger.info("Document info validation successful")
        except Exception as e:
            raise Exception(f"Document info validation failed: {str(e)}")

        return True

    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        return False

if __name__ == "__main__":
    # Run the test
    success = asyncio.run(test_document_processing())
    if success:
        logger.info("All tests passed successfully!")
    else:
        logger.error("Tests failed!") 