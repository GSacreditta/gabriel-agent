"""
Storage Agent (Vector) - Vector Database Operations Agent
Handles embedding generation, vector storage, and similarity searches
yngIntegrated with FAISS VectorStorageService for unified architecture
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import uuid
import json
from .base_agent import BaseAgent


class StorageAgent(BaseAgent):
    """Storage Agent for vector database operations using FAISS"""

    def __init__(self):
        super().__init__("STORAGE_AGENT")

        # FAISS VectorStorageService integration (injected by main app)
        self.vector_service = None

        # Configuration
        self.chunk_size = 1000

    def set_vector_service(self, vector_service):
        """Inject the FAISS VectorStorageService dependency"""
        self.vector_service = vector_service
        self.log_activity("FAISS VectorStorageService injected", {
            "service_type": type(vector_service).__name__
        })
    
    def connect_agent(self, agent_type: str, agent_instance):
        """Connect to another agent"""
        self.log_activity(f"Connected to {agent_type}", {"agent_type": agent_type})
    
    async def health_check(self) -> bool:
        """Check if the agent is healthy"""
        try:
            # Basic health check - agent is healthy if vector service is available
            return self.vector_service is not None
        except Exception as e:
            self.log_activity("Health check failed", {"error": str(e)})
            return False

    async def get_capabilities(self) -> List[str]:
        """Return Storage Agent capabilities"""
        return [
            "embedding_generation",
            "vector_storage", 
            "similarity_search",
            "collection_management",
            "metadata_storage"
        ]
    
    async def handle_message(self, source_agent: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle messages from other agents"""
        action = message.get('action')
        data = message.get('data', {})

        # Check if vector service is available
        if not self.vector_service:
            return {"status": "error", "message": "VectorStorageService not available"}

        try:
            if action == "store_extraction":
                result = await self.store_extraction_data(data)
                return {"status": "success", "result": result}

            elif action == "similarity_search":
                result = await self.similarity_search(
                    data.get('query'),
                    data.get('top_k', 5),
                    data.get('filter_metadata')
                )
                return {"status": "success", "result": result}

            elif action == "get_collection_info":
                result = await self.get_storage_info()
                return {"status": "success", "result": result}

            elif action == "collection_maintenance":
                result = await self.collection_maintenance()
                return {"status": "success", "result": result}

            else:
                return {"status": "error", "message": f"Unknown action: {action}"}

        except Exception as e:
            self.logger.error(f"Error handling message: {e}")
            return {"status": "error", "message": str(e)}
    
    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute storage tasks"""
        task_type = task.get('type')
        
        if task_type == "collection_maintenance":
            return await self.collection_maintenance()
        else:
            return {"status": "error", "message": f"Unknown task type: {task_type}"}
    
    async def store_extraction_data(self, extraction_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Store extraction data with embeddings using FAISS
        Storage Agent delegates to VectorStorageService for unified storage
        """
        try:
            if not self.vector_service:
                return {"status": "error", "message": "VectorStorageService not available"}

            file_name = extraction_data.get('file_name', '')

            self.log_activity("Storing extraction data", {
                "file_name": file_name,
                "entity_name": extraction_data.get('entity_name')
            })

            # Step 1: Create text chunks from extraction data
            chunks = await self.create_text_chunks(extraction_data)

            # Step 2: Prepare metadata using document_processor.py fields
            metadata = self.prepare_metadata(extraction_data)

            # Step 3: Store in FAISS via VectorStorageService
            doc_id_prefix = file_name.replace('.', '_').replace(' ', '_')[:20]

            # Convert chunks to documents format expected by FAISS
            documents = []
            for i, chunk in enumerate(chunks):
                documents.append({
                    "text": chunk,
                    "metadata": {
                        **metadata,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "document_id": doc_id_prefix,
                        "stored_at": datetime.utcnow().isoformat()
                    }
                })

            # Generate embeddings for documents
            texts = [doc["text"] for doc in documents]
            metadata_list = [doc["metadata"] for doc in documents]
            
            # Generate embeddings using the vector service's embedding model
            embeddings = await self.vector_service.embeddings.aembed_documents(texts)
            
            # Store documents with embeddings using FAISS service
            storage_result = await self.vector_service.add_documents(
                documents,
                embeddings,
                metadata_list
            )

            if not storage_result.get('success'):
                self.logger.error(f"Failed to store in FAISS: {storage_result}")
                return {"status": "error", "message": storage_result}

            # Step 4: Store document metadata in DB Agent
            db_response = await self.send_message("DB_AGENT", {
                "action": "store_document_metadata",
                "data": extraction_data
            })

            self.log_activity("Extraction data stored", {
                "file_name": file_name,
                "documents_stored": len(documents),
                "success": storage_result.get('success', False)
            })

            return {
                "status": "completed",
                "documents_stored": len(documents),
                "success": storage_result.get('success', False)
            }

        except Exception as e:
            self.logger.error(f"Error storing extraction data: {e}")
            return {"status": "error", "message": str(e)}
    
    async def create_text_chunks(self, extraction_data: Dict[str, Any]) -> List[str]:
        """Create text chunks from extraction data"""
        # Combine relevant text fields for chunking
        text_content = ""
        
        if extraction_data.get('subject'):
            text_content += f"Subject: {extraction_data['subject']}\n\n"
        
        if extraction_data.get('summary'):
            text_content += f"Summary: {extraction_data['summary']}\n\n"
        
        # Add other text fields if available
        if extraction_data.get('content'):
            text_content += f"Content: {extraction_data['content']}\n\n"
        
        # Simple chunking implementation
        if len(text_content) <= self.chunk_size:
            return [text_content] if text_content else ["No content available"]
        else:
            # Split into chunks with overlap
            chunks = []
            start = 0
            overlap = 100  # Character overlap between chunks
            
            while start < len(text_content):
                end = start + self.chunk_size
                chunk = text_content[start:end]
                
                # Try to break at sentence boundary
                if end < len(text_content):
                    last_period = chunk.rfind('.')
                    last_newline = chunk.rfind('\n')
                    break_point = max(last_period, last_newline)
                    
                    if break_point > start + 200:  # Minimum chunk size
                        chunk = text_content[start:break_point + 1]
                        end = break_point + 1
                
                chunks.append(chunk)
                start = end - overlap if end < len(text_content) else end
                
            return chunks
    
    def prepare_metadata(self, extraction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare metadata using same fields from document_processor.py"""
        # Ensure metadata values are serializable (Bool, Int, Float, or String)
        def safe_metadata_value(value, default=""):
            """Ensure metadata value is not None"""
            if value is None:
                return default
            if isinstance(value, (str, int, float, bool)):
                return value
            return str(value)
        
        return {
            "file_name": safe_metadata_value(extraction_data.get('file_name'), "unknown_file"),
            "entity_name": safe_metadata_value(extraction_data.get('entity_name'), "unknown_entity"),
            "issue_date": safe_metadata_value(extraction_data.get('issue_date'), ""),
            "subject": safe_metadata_value(extraction_data.get('subject'), ""),
            "document_type": safe_metadata_value(extraction_data.get('document_type'), "general_document"),
            "confidence_scores": json.dumps(extraction_data.get('confidence_scores', {})),
            "processing_time": safe_metadata_value(extraction_data.get('processing_time'), 0.0),
            "drive_link": safe_metadata_value(extraction_data.get('drive_link'), "")
        }
    
    async def similarity_search(self, query: str, top_k: int = 5, filter_metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Perform similarity search using FAISS VectorStorageService
        """
        try:
            if not self.vector_service:
                return {"status": "error", "message": "VectorStorageService not available"}

            self.log_activity("Similarity search started", {
                "query": query[:50] + "..." if len(query) > 50 else query,
                "top_k": top_k
            })

            # Use FAISS for similarity search
            search_result = await self.vector_service.search_documents(
                query=query,
                k=top_k
            )

            # VectorStorageService.search_documents returns a list[Document] currently
            if isinstance(search_result, list):
                formatted = [
                    {
                        "text": getattr(doc, "page_content", None) or getattr(doc, "text", ""),
                        "metadata": getattr(doc, "metadata", {})
                    }
                    for doc in search_result
                ]
                self.log_activity("Similarity search completed", {
                    "results_found": len(formatted)
                })
                return {
                    "status": "success",
                    "results": formatted,
                    "result_count": len(formatted)
                }

            # Fallback if service returns a dict shape
            if isinstance(search_result, dict):
                success = bool(search_result.get("success"))
                documents = search_result.get("documents") or search_result.get("results") or []
                self.log_activity("Similarity search completed", {
                    "results_found": len(documents)
                })
                return {
                    "status": "success" if success else "error",
                    "results": documents,
                    "result_count": len(documents)
                }

            # Unknown response shape
            return {"status": "error", "message": "Unexpected search result format"}

        except Exception as e:
            self.logger.error(f"Error in similarity search: {e}")
            return {"status": "error", "message": str(e)}
    
    async def collection_maintenance(self) -> Dict[str, Any]:
        """Perform collection maintenance tasks using FAISS"""
        try:
            if not self.vector_service:
                return {"status": "error", "message": "VectorStorageService not available"}

            self.log_activity("Collection maintenance started")

            # Get current storage status for maintenance info
            status = await self.vector_service.get_storage_status()

            self.log_activity("Collection maintenance completed", {
                "vector_store_active": status.get('vector_store_active', False),
                "documents_count": status.get('documents_count', 0)
            })

            return {
                "status": "success",
                "message": "FAISS collection maintenance completed",
                "storage_status": status
            }

        except Exception as e:
            self.logger.error(f"Error in collection maintenance: {e}")
            return {"status": "error", "message": str(e)}

    async def get_storage_info(self) -> Dict[str, Any]:
        """Get storage information using FAISS"""
        try:
            if not self.vector_service:
                return {"status": "error", "message": "VectorStorageService not available"}

            storage_status = await self.vector_service.get_storage_status()

            return {
                "status": "success",
                "storage_info": storage_status,
                "capabilities": await self.get_capabilities()
            }

        except Exception as e:
            self.logger.error(f"Error getting storage info: {e}")
            return {"status": "error", "message": str(e)} 