from typing import List, Dict, Any, Optional
import logging
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from ..core.config import get_settings
from pathlib import Path
import tempfile
import shutil
import os

logger = logging.getLogger(__name__)

class VectorStorageService:
    """Service for storing and retrieving document embeddings using FAISS."""
    
    def __init__(
        self,
        persist_directory: str = "faiss_db",
        index_name: str = "documents",
        use_temp_dir: bool = False
    ):
        """Initialize the vector storage service.
        
        Args:
            persist_directory (str): Directory to persist the vector database
            index_name (str): Name of the index to store documents
            use_temp_dir (bool): Whether to use a temporary directory (for tests)
        """
        try:
            self.settings = get_settings()
            
            # Set up the vector database directory
            if use_temp_dir:
                temp_base = Path(self.settings.TEMP_DIR)
                temp_base.mkdir(parents=True, exist_ok=True)
                self.temp_dir = Path(tempfile.mkdtemp(prefix="gabriel_agent_vector_", dir=temp_base))
                self.db_dir = self.temp_dir / persist_directory
            else:
                self.db_dir = Path(persist_directory)
                self.temp_dir = None
                
            self.db_dir.mkdir(parents=True, exist_ok=True)
            self.index_name = index_name
            logger.info(f"Vector database directory: {self.db_dir}")
            
            # Initialize embeddings
            self.embeddings = OpenAIEmbeddings(
                openai_api_key=self.settings.OPENAI_API_KEY,
                model="text-embedding-3-large"
            )
            
            # Try to load existing FAISS index, or initialize empty
            self.index_path = self.db_dir / f"{index_name}.faiss"
            self.vector_store = None
            self._load_or_create_index()
            
            logger.info("Vector Storage Service initialized successfully with FAISS")
        except Exception as e:
            logger.error(f"Failed to initialize Vector Storage Service: {str(e)}")
            raise

    def _load_or_create_index(self):
        """Load existing FAISS index or create a new one."""
        try:
            if self.index_path.exists():
                # Load existing index
                self.vector_store = FAISS.load_local(
                    str(self.db_dir), 
                    embeddings=self.embeddings,
                    index_name=self.index_name,
                    allow_dangerous_deserialization=True
                )
                logger.info(f"Loaded existing FAISS index from {self.index_path}")
            else:
                # Create empty index - we'll initialize it when first document is added
                self.vector_store = None
                logger.info("Will create new FAISS index when first document is added")
        except Exception as e:
            logger.warning(f"Could not load existing index: {e}. Will create new one.")
            self.vector_store = None

    def _ensure_index_exists(self, sample_text: str = "Sample text for initialization"):
        """Ensure FAISS index exists, creating it if necessary."""
        if self.vector_store is None:
            # Create initial index with a sample document
            self.vector_store = FAISS.from_texts(
                texts=[sample_text],
                embedding=self.embeddings,
                metadatas=[{"type": "initialization"}]
            )
            # Remove the sample document
            try:
                # FAISS doesn't have a direct delete method, so we'll work around this
                # by keeping track of real documents vs initialization ones
                pass
            except:
                pass

    async def cleanup(self):
        """Cleanup resources and close connections."""
        try:
            # Save the index before cleanup
            if self.vector_store is not None:
                self.vector_store.save_local(str(self.db_dir), index_name=self.index_name)
                logger.info(f"Saved FAISS index to {self.db_dir}")
            
            # Cleanup temporary directory if used
            if self.temp_dir and self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
                
            logger.info("Vector Storage Service cleaned up successfully")
        except Exception as e:
            logger.warning(f"Error during Vector Storage Service cleanup: {str(e)}")

    def __del__(self):
        """Cleanup database directory on object destruction."""
        try:
            if self.temp_dir and self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temporary directory: {str(e)}")

    async def store_document(
        self,
        file_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Mock storing a document.
        
        Args:
            file_id: Document ID
            metadata: Optional document metadata
            
        Returns:
            Dict containing mock response
        """
        logger.info(f"MOCK VECTOR - Storing document {file_id}")
        return {
            "success": True,
            "document_id": file_id,
            "stored_at": metadata.get("processed_at", "test_time")
        }

    async def search_documents(self, query: str, k: int = 5):
        """Search for similar documents."""
        try:
            logger.info(f"Searching for documents similar to: {query}")
            
            if self.vector_store is None:
                logger.info("No documents in vector store yet")
                return []
            
            results = self.vector_store.similarity_search(query=query, k=k)
            
            logger.info(f"Found {len(results)} similar documents")
            return results
            
        except Exception as e:
            logger.error(f"Error searching documents: {str(e)}")
            raise

    async def add_documents(
        self,
        documents: List[Dict[str, Any]],
        embeddings: List[List[float]],
        metadata: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Add documents to the vector store."""
        try:
            texts = [doc["text"] for doc in documents]
            
            # Ensure index exists
            if texts:
                self._ensure_index_exists(texts[0])
            
            # Add documents
            self.vector_store.add_texts(
                texts=texts,
                metadatas=metadata or [{}] * len(documents)
            )
            
            # Save index after adding documents
            self.vector_store.save_local(str(self.db_dir), index_name=self.index_name)
            
            return {
                "success": True,
                "message": f"Added {len(documents)} documents to vector store",
                "document_count": len(documents)
            }
            
        except Exception as e:
            logger.error(f"Error adding documents to vector store: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def search_similar(
        self,
        query: str,
        top_k: int = 3,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Search for similar documents using a query string."""
        try:
            if self.vector_store is None:
                return {
                    "success": True,
                    "results": [],
                    "total_results": 0
                }
            
            # FAISS doesn't support complex filtering, so we search and filter after
            search_k = top_k * 3 if where else top_k  # Get more results to filter
            results = self.vector_store.similarity_search_with_score(
                query,
                k=search_k
            )
            
            # Apply filtering if specified
            filtered_results = []
            for doc, score in results:
                if where:
                    # Simple metadata filtering
                    match = True
                    for key, value in where.items():
                        if key not in doc.metadata or doc.metadata[key] != value:
                            match = False
                            break
                    if not match:
                        continue
                        
                filtered_results.append({
                    "text": doc.page_content,
                    "metadata": doc.metadata,
                    "distance": float(score)
                })
                
                if len(filtered_results) >= top_k:
                    break
            
            return {
                "success": True,
                "results": filtered_results,
                "total_results": len(filtered_results)
            }
            
        except Exception as e:
            logger.error(f"Error searching vector store: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def delete_document(
        self,
        document_id: str
    ) -> Dict[str, Any]:
        """Delete a document from the vector store."""
        try:
            # FAISS doesn't support direct deletion, so we rebuild without the document
            logger.warning("FAISS doesn't support direct document deletion. Consider rebuilding index.")
            
            return {
                "success": True,
                "message": f"Document deletion logged for {document_id} (FAISS limitation)",
                "note": "FAISS requires index rebuild to actually remove documents"
            }
            
        except Exception as e:
            logger.error(f"Error deleting document {document_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def delete_documents(
        self,
        document_ids: List[str]
    ) -> Dict[str, Any]:
        """Delete multiple documents from the vector store."""
        try:
            logger.warning("FAISS doesn't support direct document deletion. Consider rebuilding index.")
            
            return {
                "success": True,
                "message": f"Document deletions logged for {len(document_ids)} documents (FAISS limitation)",
                "note": "FAISS requires index rebuild to actually remove documents"
            }
            
        except Exception as e:
            logger.error(f"Error deleting documents: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector collection."""
        try:
            if self.vector_store is None:
                return {
                    "total_documents": 0,
                    "embedding_dimension": 0,
                    "index_type": "FAISS (not initialized)"
                }
            
            # FAISS doesn't expose collection stats directly
            # We can get some basic info from the index
            return {
                "total_documents": "Unknown (FAISS limitation)",
                "embedding_dimension": "Unknown (FAISS limitation)", 
                "index_type": "FAISS",
                "index_path": str(self.index_path)
            }
            
        except Exception as e:
            logger.error(f"Error getting collection stats: {str(e)}")
            return {
                "error": str(e)
            }

    async def _validate_file(self, file: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Get file metadata
            metadata = await self.drive_service.get_file_metadata(file['id'])
            mime_type = metadata.get('mimeType', '')
            # Use the original file name if available, else fallback to metadata
            file_name = file.get('name', '') or metadata.get('name', '')

            # Check if file type is supported
            if mime_type in self.supported_mime_types:
                return {
                    "is_valid": True,
                    "file_type": self.supported_mime_types[mime_type]
                }

            # Fallback: check file extension for PDF
            if file_name.lower().endswith('.pdf'):
                return {
                    "is_valid": True,
                    "file_type": "PDF",
                    "reason": f"Accepted by .pdf extension despite unrecognized mime_type: {mime_type}"
                }

            return {
                "is_valid": False,
                "reason": f"Unsupported file type: {mime_type}"
            }
        except Exception as e:
            logger.error(f"Error validating file: {str(e)}")
            return {
                "is_valid": False,
                "reason": f"Validation error: {str(e)}"
            } 