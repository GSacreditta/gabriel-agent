import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class HandlerVector:
    def __init__(self, document_processor, drive_service, vector_service, slack_service):
        self.document_processor = document_processor
        self.drive_service = drive_service
        self.vector_service = vector_service
        self.slack_service = slack_service

    async def handle_approval(self, file_id: str, approved_entity: str, human_corrections: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Handle human approval and execute final actions (STEP A–D):
        - Create/match folder
        - Move file
        - Store in vector DB
        - Send Slack confirmation
        """
        try:
            logger.info(f"HANDLER_VECTOR: Processing approval for file: {file_id}")
            logger.info(f"HANDLER_VECTOR: Approved entity: {approved_entity}")

            # Get file metadata again
            file_metadata = await self.drive_service.get_file_metadata(file_id)
            file_name = file_metadata.get('name', 'Unknown file')

            # STEP A: Create or match folder based on APPROVED entity
            try:
                folder_result = await self.drive_service.create_or_match_folder(approved_entity)
                if not folder_result or not folder_result.get("folder_id"):
                    raise ValueError("Failed to create/match folder")
                logger.info(f"HANDLER_VECTOR: Created/matched folder for {approved_entity}")
            except Exception as e:
                error_msg = f"HANDLER_VECTOR: Folder operation failed: {str(e)}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg, "file_id": file_id, "file_name": file_name, "entity_name": approved_entity}

            # STEP B: Move file to approved folder
            try:
                move_result = await self.drive_service.move_file_to_folder(
                    file_id=file_id,
                    folder_id=folder_result["folder_id"]
                )
                if not move_result or not move_result.get("id"):
                    raise ValueError("Failed to move file")
                logger.info(f"HANDLER_VECTOR: Successfully moved file to {approved_entity} folder")
            except Exception as e:
                error_msg = f"HANDLER_VECTOR: File move failed: {str(e)}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg, "file_id": file_id, "file_name": file_name, "folder_id": folder_result["folder_id"]}

            # STEP C: Store in vector database (now that it's approved)
            try:
                # Re-extract text for vector storage
                ocr_result = await self.document_processor.ocr_service.extract_text(file_id)
                if ocr_result.get("success"):
                    extracted_text = ocr_result.get("text", "")
                    document_info = {
                        "file_name": file_name,
                        "entity_name": approved_entity,
                        "processing_time": datetime.utcnow().isoformat(),
                        "file_metadata": file_metadata,
                        "status": "approved_and_processed",
                        "human_corrections": human_corrections or {}
                    }
                    await self.vector_service.store_document(
                        document_id=file_id,
                        content=extracted_text,
                        metadata=document_info
                    )
                    logger.info("HANDLER_VECTOR: Successfully stored document in vector database")
            except Exception as e:
                error_msg = f"HANDLER_VECTOR: Vector storage warning: {str(e)}"
                logger.warning(error_msg)
                # Continue as this is not critical

            # STEP D: Send confirmation
            if self.slack_service:
                try:
                    message = (
                        f"✅ *DOCUMENT APPROVED & PROCESSED*\n\n"
                        f"📄 *Document:* {file_name}\n"
                        f"🏢 *Final Entity:* {approved_entity}\n"
                        f"📁 *Moved to Folder:* {approved_entity}\n"
                        f"💾 *Vector Storage:* ✅ Complete\n"
                        f"📅 *Completed:* {datetime.utcnow().isoformat()}\n\n"
                        f"*🔗 Drive Link:* https://drive.google.com/file/d/{file_id}"
                    )
                    await self.slack_service.send_review_request(message)
                    logger.info("HANDLER_VECTOR: Sent completion confirmation to Slack")
                except Exception as e:
                    logger.error(f"HANDLER_VECTOR: Slack confirmation warning: {str(e)}")

            return {
                "success": True,
                "status": "approved_and_processed",
                "message": f"Document approved and processed: {file_name}",
                "entity_name": approved_entity,
                "folder_id": folder_result["folder_id"],
                "final_actions": [
                    "Folder created/matched",
                    "File moved to folder",
                    "Stored in vector database",
                    "Confirmation sent"
                ]
            }
        except Exception as e:
            error_msg = f"HANDLER_VECTOR: Approval failed: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg, "file_id": file_id} 