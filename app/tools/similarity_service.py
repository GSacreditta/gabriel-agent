from typing import List, Dict, Any, Optional
import logging
import numpy as np
from ..services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

class SimilarityService:
    """Service for performing similarity search using document embeddings."""
    
    def __init__(self, model_name: str = "text-embedding-3-large"):
        """Initialize the similarity service.
        
        Args:
            model_name (str): The embedding model to use for queries
        """
        self.embedding_service = EmbeddingService(model_name=model_name)
        
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors.
        
        Args:
            vec1 (List[float]): First vector
            vec2 (List[float]): Second vector
            
        Returns:
            float: Cosine similarity score between 0 and 1
        """
        vec1_array = np.array(vec1)
        vec2_array = np.array(vec2)
        
        # Calculate dot product
        dot_product = np.dot(vec1_array, vec2_array)
        
        # Calculate magnitudes
        norm1 = np.linalg.norm(vec1_array)
        norm2 = np.linalg.norm(vec2_array)
        
        # Avoid division by zero
        if norm1 == 0 or norm2 == 0:
            return 0.0
            
        return dot_product / (norm1 * norm2)

    async def find_similar_chunks(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        top_k: int = 3,
        similarity_threshold: float = 0.7
    ) -> Dict[str, Any]:
        """Find chunks similar to the query text.
        
        Args:
            query (str): The search query
            chunks (List[Dict[str, Any]]): List of chunks with their embeddings
            top_k (int): Number of most similar chunks to return
            similarity_threshold (float): Minimum similarity score (0-1)
            
        Returns:
            Dict[str, Any]: Similar chunks with their similarity scores
        """
        try:
            # Generate embedding for the query
            query_result = await self.embedding_service.generate_embeddings(query)
            if not query_result["success"]:
                raise Exception(f"Failed to generate query embedding: {query_result.get('error')}")
            
            query_embedding = query_result["embeddings"]
            
            # Calculate similarities
            similarities = []
            for chunk in chunks:
                similarity = self.cosine_similarity(query_embedding, chunk["embeddings"])
                if similarity >= similarity_threshold:
                    similarities.append({
                        "chunk_index": chunk["chunk_index"],
                        "text": chunk["text"],
                        "similarity_score": similarity
                    })
            
            # Sort by similarity score and get top_k results
            similarities.sort(key=lambda x: x["similarity_score"], reverse=True)
            top_results = similarities[:top_k]
            
            return {
                "success": True,
                "query": query,
                "results": top_results,
                "total_matches": len(similarities)
            }
            
        except Exception as e:
            logger.error(f"Error in similarity search: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def find_similar_documents(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 3,
        similarity_threshold: float = 0.7
    ) -> Dict[str, Any]:
        """Find documents similar to the query text.
        
        Args:
            query (str): The search query
            documents (List[Dict[str, Any]]): List of documents with their embeddings
            top_k (int): Number of most similar documents to return
            similarity_threshold (float): Minimum similarity score (0-1)
            
        Returns:
            Dict[str, Any]: Similar documents with their similarity scores
        """
        try:
            # Generate embedding for the query
            query_result = await self.embedding_service.generate_embeddings(query)
            if not query_result["success"]:
                raise Exception(f"Failed to generate query embedding: {query_result.get('error')}")
            
            query_embedding = query_result["embeddings"]
            
            # Calculate similarities
            similarities = []
            for doc in documents:
                # Use the first chunk's embedding as document embedding
                if doc.get("chunks") and len(doc["chunks"]) > 0:
                    doc_embedding = doc["chunks"][0]["embeddings"]
                    similarity = self.cosine_similarity(query_embedding, doc_embedding)
                    
                    if similarity >= similarity_threshold:
                        similarities.append({
                            "document_id": doc.get("document_id"),
                            "title": doc.get("title", "Untitled"),
                            "similarity_score": similarity,
                            "first_chunk": doc["chunks"][0]["text"][:200] + "..."  # Preview
                        })
            
            # Sort by similarity score and get top_k results
            similarities.sort(key=lambda x: x["similarity_score"], reverse=True)
            top_results = similarities[:top_k]
            
            return {
                "success": True,
                "query": query,
                "results": top_results,
                "total_matches": len(similarities)
            }
            
        except Exception as e:
            logger.error(f"Error in document similarity search: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }