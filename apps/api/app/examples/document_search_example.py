import asyncio
import logging
from ..services.document_processor import DocumentProcessor

# Configure logging with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Example of using document processor with vector storage."""
    try:
        logger.info("Starting document processing example...")
        
        # Initialize document processor
        processor = DocumentProcessor(
            persist_directory="chroma_db",
            collection_name="example_documents"
        )
        logger.info("Document processor initialized")
        
        # Example documents
        documents = [
            {
                "id": "doc1",
                "title": "Python Programming",
                "text": """
                Python is a high-level programming language known for its simplicity and readability.
                It supports multiple programming paradigms including procedural, object-oriented, and functional programming.
                Python's extensive standard library and third-party packages make it suitable for various applications.
                """,
                "source": "example"
            },
            {
                "id": "doc2",
                "title": "Machine Learning Basics",
                "text": """
                Machine learning is a subset of artificial intelligence that focuses on developing systems
                that can learn from and make decisions based on data. It includes techniques like supervised learning,
                unsupervised learning, and reinforcement learning.
                """,
                "source": "example"
            }
        ]
        
        # Process and store documents
        logger.info("Processing documents...")
        for doc in documents:
            logger.info(f"Processing document: {doc['title']}")
            result = await processor.process_and_store_document(doc)
            if result["success"]:
                logger.info(f"Successfully processed document: {doc['title']}")
                logger.info(f"Created {result['chunk_count']} chunks")
            else:
                logger.error(f"Failed to process document: {result.get('error')}")
        
        # Example searches
        queries = [
            "What is Python?",
            "Tell me about machine learning",
            "How does programming work?"
        ]
        
        logger.info("\nStarting search examples...")
        for query in queries:
            logger.info(f"\nSearching for: {query}")
            results = await processor.search_documents(
                query=query,
                top_k=2,
                filters={"source": "example"}  # Optional filter
            )
            
            if results["success"]:
                logger.info(f"Found {results['total_results']} results:")
                for i, result in enumerate(results["results"], 1):
                    logger.info(f"\nResult {i}:")
                    logger.info(f"Text: {result['text']}")
                    logger.info(f"Score: {result['distance']}")
                    logger.info(f"Metadata: {result['metadata']}")
            else:
                logger.error(f"Search failed: {results.get('error')}")
        
        logger.info("\nExample completed successfully!")
        
    except Exception as e:
        logger.error(f"Example failed: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 