from typing import List, Dict, Any, Optional
import logging
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import os
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from ..core.config import get_settings
from pathlib import Path
import tempfile
import shutil

logger = logging.getLogger(__name__)

class VectorStorageService:
    """Service for storing and retrieving document embeddings using ChromaDB."""
    
    def __init__(self):
        """Initialize the vector storage service."""
        try:
            self.settings = get_settings()
            
            # Set up the vector database directory in a secure temp location
            self.temp_dir = Path(tempfile.mkdtemp(prefix="gabriel_agent_vector_"))
            self.db_dir = self.temp_dir / "chroma_db"
            self.db_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Vector database directory: {self.db_dir}")
            
            # Initialize embeddings
            self.embeddings = OpenAIEmbeddings(
                openai_api_key=self.settings.OPENAI_API_KEY,
                model="text-embedding-3-large"
            )
            
            # Initialize vector store
            self.vector_store = Chroma(
                persist_directory=str(self.db_dir),
                embedding_function=self.embeddings
            )
            
            logger.info("Vector Storage Service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Vector Storage Service: {str(e)}")
            raise

    def __del__(self):
        """Cleanup temporary directory on object destruction."""
        try:
            if hasattr(self, 'temp_dir') and self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temp directory: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp directory: {str(e)}")

    async def store_document(self, document_id: str, content: str, metadata: dict):
        """Store a document in the vector database."""
        try:
            logger.info(f"Storing document {document_id} in vector database")
            
            # Add document to vector store
            self.vector_store.add_texts(
                texts=[content],
                metadatas=[metadata],
                ids=[document_id]
            )
            
            # Persist changes
            self.vector_store.persist()
            
            logger.info(f"Successfully stored document {document_id}")
            
        except Exception as e:
            logger.error(f"Error storing document {document_id}: {str(e)}")
            raise

    async def search_documents(self, query: str, k: int = 5):
        """Search for similar documents."""
        try:
            logger.info(f"Searching for documents similar to: {query}")
            
            # Search vector store
            results = self.vector_store.similarity_search(
                query=query,
                k=k
            )
            
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
            # Prepare data for ChromaDB
            ids = [str(i) for i in range(len(documents))]
            texts = [doc["text"] for doc in documents]
            
            # Add documents to collection
            self.vector_store.add_texts(
                texts=texts,
                metadatas=metadata or [{}] * len(documents),
                ids=ids
            )
            
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
        query_embedding: List[float],
        top_k: int = 3,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Search for similar documents using a query embedding."""
        try:
            # Convert embedding to string for similarity search
            query_text = " ".join(map(str, query_embedding))
            
            # Perform similarity search
            results = self.vector_store.similarity_search(
                query_text,
                k=top_k,
                filter=where
            )
            
            # Format results
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "text": result.page_content,
                    "metadata": result.metadata,
                    "distance": getattr(result, 'score', 0.0)
                })
            
            return {
                "success": True,
                "results": formatted_results,
                "total_results": len(formatted_results)
            }
            
        except Exception as e:
            logger.error(f"Error searching vector store: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def delete_documents(
        self,
        document_ids: List[str]
    ) -> Dict[str, Any]:
        """Delete documents from the vector store."""
        try:
            self.vector_store.delete(ids=document_ids)
            
            return {
                "success": True,
                "message": f"Deleted {len(document_ids)} documents",
                "deleted_count": len(document_ids)
            }
            
        except Exception as e:
            logger.error(f"Error deleting documents from vector store: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the collection."""
        try:
            # Get all documents from the collection
            all_docs = self.vector_store.get()
            count = len(all_docs['ids']) if all_docs and 'ids' in all_docs else 0
            
            return {
                "success": True,
                "collection_name": "vector_store",
                "document_count": count
            }
            
        except Exception as e:
            logger.error(f"Error getting collection stats: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            } 