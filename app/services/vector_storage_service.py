from typing import List, Dict, Any, Optional
import logging
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import os

logger = logging.getLogger(__name__)

class VectorStorageService:
    """Service for storing and retrieving document embeddings using ChromaDB."""
    
    def __init__(
        self,
        persist_directory: str = "chroma_db",
        collection_name: str = "documents",
        embedding_model_name: str = "text-embedding-3-large"
    ):
        """Initialize the vector storage service.
        
        Args:
            persist_directory (str): Directory to persist the database
            collection_name (str): Name of the collection to store documents
            embedding_model_name (str): Name of the embedding model to use
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        
        # Create persist directory if it doesn't exist
        os.makedirs(persist_directory, exist_ok=True)
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity
        )
        
        logger.info(f"Initialized VectorStorageService with collection: {collection_name}")
    
    async def add_documents(
        self,
        documents: List[Dict[str, Any]],
        embeddings: List[List[float]],
        metadata: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Add documents to the vector store.
        
        Args:
            documents (List[Dict[str, Any]]): List of documents to add
            embeddings (List[List[float]]): List of document embeddings
            metadata (Optional[List[Dict[str, Any]]]): Optional metadata for each document
            
        Returns:
            Dict[str, Any]: Result of the operation
        """
        try:
            # Prepare data for ChromaDB
            ids = [str(i) for i in range(len(documents))]
            texts = [doc["text"] for doc in documents]
            
            # Add documents to collection
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadata or [{}] * len(documents)
            )
            
            return {
                "success": True,
                "message": f"Added {len(documents)} documents to collection",
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
        """Search for similar documents using a query embedding.
        
        Args:
            query_embedding (List[float]): Query embedding vector
            top_k (int): Number of results to return
            where (Optional[Dict[str, Any]]): Filter conditions
            
        Returns:
            Dict[str, Any]: Search results
        """
        try:
            # Perform similarity search
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where
            )
            
            # Format results
            formatted_results = []
            for i in range(len(results["ids"][0])):
                formatted_results.append({
                    "id": results["ids"][0][i],
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i] if "distances" in results else None
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
        """Delete documents from the vector store.
        
        Args:
            document_ids (List[str]): IDs of documents to delete
            
        Returns:
            Dict[str, Any]: Result of the operation
        """
        try:
            self.collection.delete(ids=document_ids)
            
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
        """Get statistics about the collection.
        
        Returns:
            Dict[str, Any]: Collection statistics
        """
        try:
            count = self.collection.count()
            
            return {
                "success": True,
                "collection_name": self.collection_name,
                "document_count": count
            }
            
        except Exception as e:
            logger.error(f"Error getting collection stats: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            } 