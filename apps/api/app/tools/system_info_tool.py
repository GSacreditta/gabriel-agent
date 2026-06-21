"""
System Information Tool - Provides agent with awareness of available data sources and capabilities
"""

from langchain.tools import BaseTool
from typing import Dict, Any, Optional
import logging
import json

logger = logging.getLogger(__name__)

class SystemInfoTool(BaseTool):
    """Tool to provide system awareness and data source information to the agent."""
    
    name: str = "system_info"
    description: str = """Get information about available data sources, tools, and system capabilities.
    Use this tool to understand what data sources are available and how to query them.
    
    Input should be one of:
    - "data_sources" - List all available data sources
    - "capabilities" - List agent capabilities and tools
    - "entity_search" - How to search for entity information
    - "api_endpoints" - Available API endpoints
    - "query_strategy" - Best practices for finding information
    """
    
    def _run(self, query: str) -> str:
        """Execute the system info query."""
        try:
            query = query.lower().strip()
            
            if query == "data_sources":
                return self._get_data_sources()
            elif query == "capabilities":
                return self._get_capabilities()
            elif query == "entity_search":
                return self._get_entity_search_strategy()
            elif query == "api_endpoints":
                return self._get_api_endpoints()
            elif query == "query_strategy":
                return self._get_query_strategy()
            else:
                return self._get_general_info()
                
        except Exception as e:
            logger.error(f"Error in SystemInfoTool: {e}")
            return f"Error retrieving system information: {str(e)}"
    
    def _get_data_sources(self) -> str:
        """Return information about available data sources."""
        return """
🗄️ **Available Data Sources:**

1. **PostgreSQL Database** (Primary entity storage)
   - Entity information (names, categories, metadata)
   - Task management
   - Relationships and references
   - Access via: DB_AGENT through Agent Coordinator

2. **Google Drive** (Document storage)
   - PDF documents, images, spreadsheets
   - Organized in entity folders
   - File metadata and content
   - Access via: DriveTool

3. **ChromaDB Vector Database** (Document embeddings)
   - Document content search
   - Semantic similarity
   - Entity-document relationships
   - Access via: /chromadb/search API

4. **Google Sheets** (Structured data)
   - Spreadsheet data processing
   - Export/import capabilities
   - Access via: Sheet tools

**Query Priority:**
1. Database first (for entity info)
2. Vector DB (for document content)
3. Google Drive (for file details)
4. Sheets (for structured data)
"""

    def _get_capabilities(self) -> str:
        """Return information about agent capabilities."""
        return """
🤖 **Agent Capabilities:**

**Multi-Agent System:**
- DB_AGENT: Database operations (entities, tasks)
- EXTRACTION_AGENT: Document content extraction
- HDL_AGENT: Human approval workflows
- SCHEDULER_AGENT: Automated tasks

**Available Tools:**
- OCRTool: Text extraction from images/PDFs
- DriveTool: Google Drive operations
- Sheet Tools: Google Sheets read/write
- System Info: Capability awareness (this tool)

**Core Functions:**
- Entity management (create, read, update, search)
- Document processing and extraction
- Human review workflows
- Task scheduling and management
- File organization and storage

**Integration Points:**
- Slack notifications and interactions
- Google Drive automation
- Database persistence
- Vector search capabilities
"""

    def _get_entity_search_strategy(self) -> str:
        """Return the best strategy for searching entity information."""
        return """
🔍 **Entity Search Strategy:**

**For Entity Information (like "Trust Stern"):**

1. **Primary: Database Search**
   - Use Agent Coordinator to query DB_AGENT
   - Actions: "list_entities", "match_entity", "get_entity"
   - Most reliable and complete source

2. **Secondary: Vector Database**
   - Search for documents containing entity name
   - Use /chromadb/search API with entity name
   - Find related documents and context

3. **Tertiary: Google Drive**
   - Search for folders/files with entity name
   - Use DriveTool search functionality
   - Check folder structure and file names

**Example Entity Query Process:**
1. Query database: "Does entity 'Trust Stern' exist?"
2. If not found: "Search vector DB for documents mentioning 'Trust Stern'"
3. If still not found: "Search Google Drive for 'Trust Stern' folders/files"
4. Provide comprehensive results from all sources

**Never assume absence** - always check multiple sources before concluding entity doesn't exist.
"""

    def _get_api_endpoints(self) -> str:
        """Return available API endpoints."""
        return """
🌐 **Available API Endpoints:**

**Entity Management:**
- GET /entities - List all entities
- POST /entities - Create new entity
- GET /entities/{id} - Get specific entity
- POST /entities/match - Match entity by name

**Task Management:**
- GET /tasks - List tasks (with filters)
- POST /tasks - Create new task
- PUT /tasks/{id}/status - Update task status

**Document Processing:**
- POST /extraction/extract-document - Extract content
- POST /chromadb/search - Vector search
- POST /chromadb/store - Store document

**File Operations:**
- POST /files/scan - Scan Google Drive
- GET /files/inventory - File inventory
- POST /folders/create/{entity_name} - Create entity folder

**Agent Communication:**
- GET /agents/status - Agent health
- POST /agents/message - Send message to agent
- GET /agents/capabilities - Agent capabilities

**Health & Testing:**
- GET /health - System health
- GET /chromadb/info - Vector DB status
"""

    def _get_query_strategy(self) -> str:
        """Return best practices for information queries."""
        return """
📋 **Query Strategy Best Practices:**

**When User Asks About Entity:**
1. Check database first using Agent Coordinator
2. Search vector database for related documents
3. Look in Google Drive for entity folders
4. Combine results for comprehensive answer

**When User Asks About Files/Documents:**
1. Use vector database semantic search
2. Check Google Drive file inventory
3. Query database for related entity information

**When User Asks About Tasks:**
1. Query database via DB_AGENT
2. Filter by entity, status, or date as needed
3. Provide actionable information

**Error Handling:**
- If one source fails, try alternatives
- Always explain what sources were checked
- Suggest specific actions if information not found

**Response Format:**
- Always mention which data sources were checked
- Provide specific next steps if information missing
- Offer alternative search terms or approaches
"""

    def _get_general_info(self) -> str:
        """Return general system information."""
        return """
ℹ️ **Gabriel Agent System Overview:**

**Purpose:** AI-powered document processing and entity management system

**Core Architecture:**
- Multi-agent system with specialized agents
- Database-backed entity storage
- Vector database for document search
- Google Drive integration
- Slack-based human interaction

**Data Flow:**
1. Documents → Processing → Extraction
2. Entity Recognition → Database Storage
3. Human Review → Approval/Correction
4. Final Storage → Vector Database + Drive Organization

**Key Principles:**
- Database as primary entity source
- Multi-source verification for accuracy
- Human-in-the-loop for important decisions
- Comprehensive logging and traceability

For specific queries, use: "data_sources", "capabilities", "entity_search", "api_endpoints", or "query_strategy"
"""

    async def _arun(self, query: str) -> str:
        """Async version of the tool."""
        return self._run(query) 