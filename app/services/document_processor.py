# app/services/document_processor.py

from typing import Dict, Any, List, Optional
import logging
from .vector_storage_service import VectorStorageService
from .embedding_service import EmbeddingService
from datetime import datetime
from .ocr_service import OCRService
from .google_drive import GoogleDriveService
from .agent import Agent
from .slack_service import SlackService
import json

logger = logging.getLogger(__name__)

class DocumentProcessorService:
    """Service for processing documents and managing the processing workflow."""
    
    def __init__(self):
        """Initialize the document processor service."""
        self.ocr_service: Optional[OCRService] = None
        self.vector_service: Optional[VectorStorageService] = None
        self.drive_service: Optional[GoogleDriveService] = None
        self.agent: Optional[Agent] = None
        self.slack_service: Optional[SlackService] = None
        logger.info("Document Processor Service initialized")

    async def initialize(
        self,
        ocr_service: OCRService,
        vector_service: VectorStorageService,
        drive_service: GoogleDriveService,
        agent: Agent,
        slack_service: SlackService
    ):
        """Initialize the service with required dependencies."""
        self.ocr_service = ocr_service
        self.vector_service = vector_service
        self.drive_service = drive_service
        self.agent = agent
        self.slack_service = slack_service
        logger.info("Document Processor Service initialized with dependencies")

    async def process_document(self, file_id: str) -> Dict[str, Any]:
        """
        Process a document through the complete workflow.
        
        Args:
            file_id (str): Google Drive file ID
            
        Returns:
            Dict[str, Any]: Processing result
        """
        try:
            logger.info(f"Starting document processing for file: {file_id}")
            
            # Validate dependencies
            missing_services = []
            if not self.ocr_service:
                missing_services.append("OCR Service")
            if not self.vector_service:
                missing_services.append("Vector Storage Service")
            if not self.drive_service:
                missing_services.append("Drive Service")
            if not self.agent:
                missing_services.append("Agent")
            
            if missing_services:
                error_msg = f"Required services not initialized: {', '.join(missing_services)}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "missing_services": missing_services
                }
            
            # Get file metadata
            try:
                file_metadata = await self.drive_service.get_file_metadata(file_id)
                if not file_metadata:
                    raise ValueError("No metadata returned for file")
                
                file_name = file_metadata.get('name', 'Unknown file')
                mime_type = file_metadata.get('mimeType', '')
                logger.info(f"Processing file: {file_name} (Type: {mime_type})")
            except Exception as e:
                error_msg = f"Failed to get file metadata: {str(e)}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "file_id": file_id
                }
            
            # Step 1: Handle file based on type
            try:
                if "google-apps" in mime_type:
                    logger.info(f"Processing Google Workspace file: {file_name}")
                    file_content = await self.drive_service.export_file(file_id, "application/pdf")
                    logger.info("Successfully exported Google Workspace file to PDF")
                else:
                    logger.info(f"Processing regular file: {file_name}")
                    file_content = await self.drive_service.download_file(file_id)
                    logger.info("Successfully downloaded file")
            except Exception as e:
                error_msg = f"File processing failed: {str(e)}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "file_id": file_id,
                    "file_name": file_name,
                    "mime_type": mime_type
                }
            
            # Step 2: Process with OCR
            logger.info("Processing document with OCR...")
            try:
                ocr_result = await self.ocr_service.process_document(file_id)
                
                if not ocr_result.get("success"):
                    logger.error(f"OCR processing failed: {ocr_result.get('error')}")
                    return {
                        "success": False,
                        "error": f"OCR processing failed: {ocr_result.get('error')}",
                        "file_id": file_id
                    }
                
                # Parse OCR result if needed
                if isinstance(ocr_result, str):
                    try:
                        ocr_result = json.loads(ocr_result)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse OCR result: {str(e)}")
                        return {
                            "success": False,
                            "error": f"Failed to parse OCR result: {str(e)}",
                            "file_id": file_id
                        }
                
                logger.info("OCR processing completed successfully")
            except Exception as e:
                logger.error(f"OCR processing failed with unexpected error: {str(e)}")
                return {
                    "success": False,
                    "error": str(e),
                    "file_id": file_id
                }
            
            # Step 3: Extract structured information
            extracted_text = ocr_result.get("data", {}).get("text", "")
            logger.info(f"Extracted text length: {len(extracted_text)} characters")
            
            # Create document info matching test structure
            document_info = {
                "file_name": file_name,
                "entity_name": ocr_result.get("data", {}).get("extracted_fields", {}).get("entity_name", "Unknown"),
                "processing_time": datetime.utcnow().isoformat(),
                "ocr_result": ocr_result,
                "extracted_text": extracted_text,
                "file_metadata": file_metadata,
                "mime_type": mime_type,
                "file_id": file_id
            }
            
            # Validate required fields
            if not document_info["entity_name"] or document_info["entity_name"] == "Unknown":
                logger.warning("Entity name not found in document")
            
            # Step 4: Plan review tasks
            try:
                review_tasks = await self.agent.plan_review_tasks(document_info)
                if not review_tasks:
                    logger.warning("No review tasks generated")
                    review_tasks = ["Error planning review tasks"]
                logger.info(f"Generated {len(review_tasks)} review tasks")
            except Exception as e:
                error_msg = f"Failed to plan review tasks: {str(e)}"
                logger.error(error_msg)
                review_tasks = [f"Error: {error_msg}"]
            
            # Step 5: Create or match folder
            try:
                folder_result = await self.drive_service.create_or_match_folder(document_info["entity_name"])
                if not folder_result or not folder_result.get("folder_id"):
                    raise ValueError("Failed to create/match folder")
                logger.info(f"Successfully created/matched folder for {document_info['entity_name']}")
            except Exception as e:
                error_msg = f"Folder operation failed: {str(e)}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "file_id": file_id,
                    "file_name": file_name,
                    "entity_name": document_info["entity_name"]
                }
            
            # Step 6: Move file to folder
            try:
                move_result = await self.drive_service.move_file_to_folder(
                    file_id=file_id,
                    folder_id=folder_result["folder_id"]
                )
                if not move_result.get("success"):
                    raise ValueError("Failed to move file")
                logger.info(f"Successfully moved file to folder")
            except Exception as e:
                error_msg = f"File move operation failed: {str(e)}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "file_id": file_id,
                    "file_name": file_name,
                    "folder_id": folder_result["folder_id"]
                }
            
            # Step 7: Store in vector database
            try:
                await self.vector_service.store_document(
                    document_id=file_id,
                    content=extracted_text,
                    metadata=document_info
                )
                logger.info("Successfully stored document in vector database")
            except Exception as e:
                error_msg = f"Vector storage failed: {str(e)}"
                logger.error(error_msg)
                # Continue as this is not critical
            
            # Step 8: Send notification
            if self.slack_service:
                try:
                    # Format message exactly as tested
                    message = (
                        f"*New Document Processed*\n\n"
                        f"*Entity:* {document_info['entity_name']}\n"
                        f"*Document:* {file_name}\n"
                        f"*Date:* {document_info['processing_time']}\n"
                        f"*Type:* {mime_type}\n\n"
                        f"*Review Tasks:*\n" + "\n".join([f"• {task}" for task in review_tasks]) + "\n\n"
                        f"*Drive Link:* https://drive.google.com/file/d/{file_id}"
                    )
                    
                    await self.slack_service.send_review_request(message)
                    logger.info("Successfully sent Slack notification")
                except Exception as e:
                    logger.error(f"Slack notification failed: {str(e)}")
                    # Continue as this is not critical
            
            return {
                "success": True,
                "message": f"Successfully processed document: {file_name}",
                "entity_name": document_info["entity_name"],
                "review_tasks": review_tasks,
                "document_info": document_info
            }
            
        except Exception as e:
            error_msg = f"Error processing document: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "file_id": file_id
            }

class DocumentProcessor:
    """Service for processing and storing documents with vector search capabilities."""
    
    def __init__(
        self,
        persist_directory: str = "chroma_db",
        collection_name: str = "documents"
    ):
        """Initialize the document processor.
        
        Args:
            persist_directory (str): Directory to persist the vector database
            collection_name (str): Name of the collection to store documents
        """
        self.vector_store = VectorStorageService(
            persist_directory=persist_directory,
            collection_name=collection_name
        )
        self.embedding_service = EmbeddingService()
        
    async def process_and_store_document(
        self,
        document: Dict[str, Any],
        chunk_size: int = 1000,
        overlap: int = 200
    ) -> Dict[str, Any]:
        """Process a document and store it in the vector database.
        
        Args:
            document (Dict[str, Any]): Document to process
            chunk_size (int): Size of text chunks
            overlap (int): Overlap between chunks
            
        Returns:
            Dict[str, Any]: Result of the operation
        """
        try:
            # Extract text from document
            text = document.get("text", "")
            if not text:
                raise ValueError("Document must contain 'text' field")
            
            # Split text into chunks
            chunks = self._split_text_into_chunks(text, chunk_size, overlap)
            
            # Generate embeddings for chunks
            chunk_documents = []
            chunk_embeddings = []
            chunk_metadata = []
            
            for i, chunk in enumerate(chunks):
                # Generate embedding
                embedding_result = await self.embedding_service.generate_embeddings(chunk)
                if not embedding_result["success"]:
                    raise Exception(f"Failed to generate embedding for chunk {i}: {embedding_result.get('error')}")
                
                # Prepare chunk data
                chunk_documents.append({"text": chunk})
                chunk_embeddings.append(embedding_result["embeddings"])
                chunk_metadata.append({
                    "document_id": document.get("id", "unknown"),
                    "title": document.get("title", "Untitled"),
                    "chunk_index": i,
                    "source": document.get("source", "unknown")
                })
            
            # Store chunks in vector database
            store_result = await self.vector_store.add_documents(
                documents=chunk_documents,
                embeddings=chunk_embeddings,
                metadata=chunk_metadata
            )
            
            if not store_result["success"]:
                raise Exception(f"Failed to store document chunks: {store_result.get('error')}")
            
            return {
                "success": True,
                "message": f"Processed and stored document with {len(chunks)} chunks",
                "chunk_count": len(chunks),
                "document_id": document.get("id")
            }
            
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def search_documents(
        self,
        query: str,
        top_k: int = 3,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Search for documents similar to the query.
        
        Args:
            query (str): Search query
            top_k (int): Number of results to return
            filters (Optional[Dict[str, Any]]): Filter conditions
            
        Returns:
            Dict[str, Any]: Search results
        """
        try:
            # Generate query embedding
            query_result = await self.embedding_service.generate_embeddings(query)
            if not query_result["success"]:
                raise Exception(f"Failed to generate query embedding: {query_result.get('error')}")
            
            # Search vector store
            search_result = await self.vector_store.search_similar(
                query_embedding=query_result["embeddings"],
                top_k=top_k,
                where=filters
            )
            
            if not search_result["success"]:
                raise Exception(f"Search failed: {search_result.get('error')}")
            
            return {
                "success": True,
                "query": query,
                "results": search_result["results"],
                "total_results": search_result["total_results"]
            }
            
        except Exception as e:
            logger.error(f"Error searching documents: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _split_text_into_chunks(
        self,
        text: str,
        chunk_size: int,
        overlap: int
    ) -> List[str]:
        """Split text into overlapping chunks.
        
        Args:
            text (str): Text to split
            chunk_size (int): Size of each chunk
            overlap (int): Overlap between chunks
            
        Returns:
            List[str]: List of text chunks
        """
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = start + chunk_size
            if end > text_length:
                end = text_length
            
            chunk = text[start:end]
            chunks.append(chunk)
            
            start = end - overlap
        
        return chunks