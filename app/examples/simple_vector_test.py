import asyncio
import logging
from ..services.vector_storage_service import VectorStorageService
from ..services.embedding_service import EmbeddingService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_single_document():
    """Test with a single small document."""
    try:
        logger.info("Starting simple vector test...")
        
        # Initialize services
        vector_store = VectorStorageService(
            persist_directory="test_chroma_db",
            collection_name="test_documents"
        )
        embedding_service = EmbeddingService()
        
        # Single test document
        test_doc = {
            "text": "Python is a popular programming language.",
            "metadata": {"source": "test"}
        }
        
        # Generate embedding
        logger.info("Generating embedding...")
        embedding_result = await embedding_service.generate_embeddings(test_doc["text"])
        if not embedding_result["success"]:
            raise Exception(f"Failed to generate embedding: {embedding_result.get('error')}")
        
        # Store document
        logger.info("Storing document...")
        store_result = await vector_store.add_documents(
            documents=[test_doc],
            embeddings=[embedding_result["embeddings"]],
            metadata=[test_doc["metadata"]]
        )
        
        if not store_result["success"]:
            raise Exception(f"Failed to store document: {store_result.get('error')}")
        
        logger.info("Document stored successfully")
        
        # Simple search
        logger.info("Testing search...")
        search_result = await vector_store.search_similar(
            query_embedding=embedding_result["embeddings"],
            top_k=1
        )
        
        if search_result["success"]:
            logger.info("Search successful!")
            logger.info(f"Found {len(search_result['results'])} results")
            for result in search_result["results"]:
                logger.info(f"Text: {result['text']}")
                logger.info(f"Score: {result['distance']}")
        else:
            logger.error(f"Search failed: {search_result.get('error')}")
        
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_single_document())
    if success:
        logger.info("Test completed successfully!")
    else:
        logger.error("Test failed!") 