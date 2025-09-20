"""
Vector Search Tool - Direct vector database search for existing document content
"""

from langchain.tools import BaseTool
from typing import Optional, Type, Dict, Any
from pydantic import BaseModel, Field
import logging
import json

logger = logging.getLogger(__name__)

class VectorSearchInput(BaseModel):
    """Input for vector search tool."""
    query: str = Field(..., description="Search query to find existing document content")
    top_k: int = Field(default=5, description="Number of top results to return")

class VectorSearchTool(BaseTool):
    """Tool for searching existing document content in the vector database."""
    
    name: str = "vector_search"
    description: str = """Search for existing document content in the vector database before processing new documents. 
    Use this FIRST when users ask for document extracts to check if the content is already available.
    Input should be a search query related to the document name or content."""
    args_schema: Type[BaseModel] = VectorSearchInput
    agent_coordinator: Optional[Any] = None  # Will be injected by main.py

    def set_agent_coordinator(self, agent_coordinator):
        """Inject the agent coordinator for internal communication."""
        self.agent_coordinator = agent_coordinator

    async def _arun(self, query: str, top_k: int = 5) -> str:
        """Search vector database asynchronously."""
        try:
            if not self.agent_coordinator:
                return "Error: Agent coordinator not available - vector search not initialized"

            logger.info(f"VectorSearchTool: Searching for '{query}' (top_k={top_k})")
            
            # Use internal agent coordinator to query STORAGE_AGENT
            # Fixed: Use existing event loop instead of creating new one
            result = await self.agent_coordinator.route_message(
                "VECTOR_SEARCH_TOOL",
                "STORAGE_AGENT",
                {
                    "action": "similarity_search",
                    "data": {
                        "query": query,
                        "top_k": top_k
                    }
                }
            )
            
            if result and result.get("status") == "success":
                search_results = result.get("result", {})
                
                # Format results for the agent
                if search_results.get("documents"):
                    documents = search_results["documents"]
                    formatted_results = []
                    
                    for i, doc in enumerate(documents[:top_k]):
                        score = search_results.get("scores", [0])[i] if i < len(search_results.get("scores", [])) else 0
                        metadata = doc.get("metadata", {})
                        content_preview = doc.get("content", "")[:200] + "..." if len(doc.get("content", "")) > 200 else doc.get("content", "")
                        
                        formatted_results.append({
                            "rank": i + 1,
                            "similarity_score": f"{score:.3f}",
                            "document_name": metadata.get("file_name", "Unknown"),
                            "document_type": metadata.get("document_type", "Unknown"),
                            "chunk_info": f"Chunk {metadata.get('chunk_index', 0) + 1}/{metadata.get('total_chunks', 1)}",
                            "content_preview": content_preview,
                            "full_content": doc.get("content", "")
                        })
                    
                    if formatted_results:
                        response = f"✅ FOUND {len(formatted_results)} relevant document(s) in vector database:\n\n"
                        
                        for result in formatted_results:
                            response += f"📄 **{result['document_name']}** (Score: {result['similarity_score']})\n"
                            response += f"   Type: {result['document_type']} | {result['chunk_info']}\n"
                            response += f"   Content: {result['content_preview']}\n\n"
                        
                        # If high similarity score, include full content
                        best_match = formatted_results[0]
                        if float(best_match["similarity_score"]) > 0.8:
                            response += f"🎯 **HIGH CONFIDENCE MATCH**: Here's the content from {best_match['document_name']}:\n\n"
                            response += f"{best_match['full_content']}\n\n"
                            response += "💡 This content was retrieved from the vector database - no need to reprocess the document!"
                        
                        return response
                    else:
                        return f"❌ No relevant documents found in vector database for query: '{query}'"
                else:
                    return f"❌ No documents found in vector database for query: '{query}'"
            else:
                return f"❌ Vector search failed: {result.get('message', 'Unknown error') if result else 'No response'}"
                
        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            return f"Error searching vector database: {str(e)}"

    def _run(self, query: str, top_k: int = 5) -> str:
        """Synchronous version not supported."""
        raise NotImplementedError("Vector search tool does not support synchronous execution")
