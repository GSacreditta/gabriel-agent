import asyncio
import logging
from app.services.vector_storage_service import VectorStorageService
from app.services.embedding_service import EmbeddingService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_vector_storage():
    """Test the vector storage functionality."""
    try:
        # Initialize services
        vector_store = VectorStorageService(
            persist_directory="test_documents",
            collection_name="test_collection",
            use_temp_dir=True
        )
        embedding_service = EmbeddingService()

        # Test documents
        test_documents = [
            {"text": "The quick brown fox jumps over the lazy dog."},
            {"text": "Python is a popular programming language."},
            {"text": "Machine learning is transforming technology."}
        ]

        # Generate embeddings
        embeddings = []
        for doc in test_documents:
            result = await embedding_service.generate_embeddings(doc["text"])
            if result["success"]:
                embeddings.append(result["embeddings"])
            else:
                raise Exception(f"Failed to generate embedding: {result.get('error')}")

        # Add documents to vector store
        add_result = await vector_store.add_documents(
            documents=test_documents,
            embeddings=embeddings,
            metadata=[{"source": f"test_{i}"} for i in range(len(test_documents))]
        )
        logger.info(f"Add documents result: {add_result}")
        if not add_result["success"]:
            raise Exception(f"Failed to add documents: {add_result.get('error')}")

        # Get collection stats
        stats = vector_store.get_collection_stats()
        logger.info(f"Collection stats: {stats}")
        if not stats["success"]:
            raise Exception(f"Failed to get collection stats: {stats.get('error')}")

        # Test search
        query = "What is Python?"
        query_result = await embedding_service.generate_embeddings(query)
        if not query_result["success"]:
            raise Exception(f"Failed to generate query embedding: {query_result.get('error')}")

        search_result = await vector_store.search_similar(
            query_embedding=query_result["embeddings"],
            top_k=2
        )
        logger.info(f"Search results for '{query}':")
        if not search_result["success"]:
            raise Exception(f"Failed to search documents: {search_result.get('error')}")
            
        for result in search_result.get("results", []):
            logger.info(f"- Text: {result.get('text', 'N/A')}")
            logger.info(f"  Score: {result.get('distance', 'N/A')}")
            logger.info(f"  Metadata: {result.get('metadata', {})}")

        # Clean up test data
        delete_result = await vector_store.delete_documents(
            document_ids=[str(i) for i in range(len(test_documents))]
        )
        logger.info(f"Delete documents result: {delete_result}")
        if not delete_result["success"]:
            raise Exception(f"Failed to delete documents: {delete_result.get('error')}")

        return True

    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        return False

if __name__ == "__main__":
    # Run the test
    success = asyncio.run(test_vector_storage())
    if success:
        logger.info("All tests passed successfully!")
    else:
        logger.error("Tests failed!") 