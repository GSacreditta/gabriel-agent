import asyncio
import logging
from ..utils.table_converter import TableConverter
from ..services.vector_storage_service import VectorStorageService
from ..services.embedding_service import EmbeddingService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_table_conversion():
    """Test table conversion and vector storage."""
    try:
        logger.info("Starting table conversion test...")
        
        # Example table data
        tables = [
            {
                "title": "Employee Information",
                "headers": ["Name", "Department", "Role", "Years"],
                "data": [
                    {"Name": "John Doe", "Department": "Engineering", "Role": "Developer", "Years": "5"},
                    {"Name": "Jane Smith", "Department": "Marketing", "Role": "Manager", "Years": "3"},
                    {"Name": "Bob Johnson", "Department": "Sales", "Role": "Representative", "Years": "2"}
                ],
                "metadata": {"source": "HR Database", "last_updated": "2024-03-15"}
            },
            {
                "title": "Project Status",
                "headers": ["Project", "Status", "Progress", "Deadline"],
                "data": [
                    ["Website Redesign", "In Progress", "75%", "2024-04-01"],
                    ["Mobile App", "Planning", "10%", "2024-06-15"],
                    ["Database Migration", "Completed", "100%", "2024-02-28"]
                ],
                "metadata": {"source": "Project Management", "department": "IT"}
            }
        ]
        
        # Convert tables to text
        logger.info("Converting tables to text...")
        table_text = TableConverter.tables_to_text(tables)
        logger.info("\nConverted text:\n" + table_text)
        
        # Initialize services
        vector_store = VectorStorageService(
            persist_directory="test_chroma_db",
            collection_name="test_tables"
        )
        embedding_service = EmbeddingService()
        
        # Generate embedding
        logger.info("Generating embedding...")
        embedding_result = await embedding_service.generate_embeddings(table_text)
        if not embedding_result["success"]:
            raise Exception(f"Failed to generate embedding: {embedding_result.get('error')}")
        
        # Store in vector database
        logger.info("Storing in vector database...")
        store_result = await vector_store.add_documents(
            documents=[{"text": table_text}],
            embeddings=[embedding_result["embeddings"]],
            metadata=[{"source": "test_tables", "table_count": len(tables)}]
        )
        
        if not store_result["success"]:
            raise Exception(f"Failed to store tables: {store_result.get('error')}")
        
        # Test search
        test_queries = [
            "Who is the marketing manager?",
            "What is the status of the website redesign?",
            "Show me all completed projects"
        ]
        
        for query in test_queries:
            logger.info(f"\nSearching for: {query}")
            query_result = await embedding_service.generate_embeddings(query)
            if not query_result["success"]:
                raise Exception(f"Failed to generate query embedding: {query_result.get('error')}")
            
            search_result = await vector_store.search_similar(
                query_embedding=query_result["embeddings"],
                top_k=1
            )
            
            if search_result["success"]:
                logger.info("Search results:")
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
    success = asyncio.run(test_table_conversion())
    if success:
        logger.info("Test completed successfully!")
    else:
        logger.error("Test failed!") 