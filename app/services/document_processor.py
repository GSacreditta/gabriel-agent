# app/services/document_processor.py

from typing import Dict, Any, List, Optional
import logging
from .vector_storage_service import VectorStorageService
from .embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

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