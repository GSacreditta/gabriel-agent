# app/services/embedding_service.py

from typing import List, Dict, Any, Optional
import logging
import numpy as np
from langchain_community.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from ..core.config import get_settings

logger = logging.getLogger(__name__)

class EmbeddingService:
    """Service for generating document embeddings using various embedding models."""
    
    def __init__(self, model_name: str = "text-embedding-ada-002"):
        """Initialize the embedding service.
        
        Args:
            model_name (str): The name of the embedding model to use.
                Options:
                - text-embedding-ada-002 (default)
                - text-embedding-3-small
                - text-embedding-3-large
        """
        try:
            self.settings = get_settings()
            
            # Initialize OpenAI embeddings with specified model
            self.embeddings = OpenAIEmbeddings(
                model=model_name,
                openai_api_key=self.settings.OPENAI_API_KEY
            )
            
            # Initialize text splitter with optimized settings
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
                separators=["\n\n", "\n", ".", "!", "?", ";", ":", " ", ""]
            )
            
            logger.info(f"Embedding Service initialized successfully with model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Embedding Service: {str(e)}")
            raise

    def normalize_vector(self, vector: List[float]) -> List[float]:
        """Normalize a vector to unit length using L2 normalization.
        
        Args:
            vector (List[float]): The input vector to normalize
            
        Returns:
            List[float]: The normalized vector
        """
        vector_array = np.array(vector)
        norm = np.linalg.norm(vector_array)
        if norm == 0:
            return vector
        return (vector_array / norm).tolist()

    async def generate_embeddings(self, text: str, normalize: bool = True) -> Dict[str, Any]:
        """Generate embeddings for a text.
        
        Args:
            text (str): The text to generate embeddings for
            normalize (bool): Whether to normalize the embedding vector
            
        Returns:
            Dict[str, Any]: Dictionary containing the embedding results
        """
        try:
            # Generate embeddings
            embeddings = await self.embeddings.aembed_query(text)
            
            # Normalize if requested
            if normalize:
                embeddings = self.normalize_vector(embeddings)
            
            return {
                "success": True,
                "embeddings": embeddings,
                "model": self.embeddings.model
            }
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def generate_document_embeddings(
        self, 
        text: str, 
        normalize: bool = True,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate embeddings for a document by chunking and embedding each chunk.
        
        Args:
            text (str): The document text to process
            normalize (bool): Whether to normalize the embedding vectors
            chunk_size (Optional[int]): Override default chunk size
            chunk_overlap (Optional[int]): Override default chunk overlap
            
        Returns:
            Dict[str, Any]: Dictionary containing the chunked embeddings
        """
        try:
            # Override chunk settings if provided
            if chunk_size or chunk_overlap:
                self.text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=chunk_size or 1000,
                    chunk_overlap=chunk_overlap or 200,
                    length_function=len,
                    separators=["\n\n", "\n", ".", "!", "?", ";", ":", " ", ""]
                )
            
            # Split text into chunks
            chunks = self.text_splitter.split_text(text)
            
            # Generate embeddings for each chunk
            chunk_embeddings = []
            for i, chunk in enumerate(chunks):
                result = await self.generate_embeddings(chunk, normalize)
                
                if result["success"]:
                    chunk_embeddings.append({
                        "chunk_index": i,
                        "text": chunk,
                        "embeddings": result["embeddings"],
                        "model": result["model"]
                    })
                else:
                    logger.warning(f"Failed to generate embeddings for chunk {i}")
            
            return {
                "success": True,
                "chunks": chunk_embeddings,
                "total_chunks": len(chunks),
                "model": self.embeddings.model
            }
            
        except Exception as e:
            logger.error(f"Error generating document embeddings: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }