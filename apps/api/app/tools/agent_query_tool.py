"""
Agent Query Tool - Allows main agent to query other agents and data sources
"""

from langchain.tools import BaseTool
from typing import Dict, Any, Optional
import logging
import json
import asyncio
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class AgentQueryTool(BaseTool):
    """Tool to query other agents and data sources through the system using internal agent coordinator."""
    
    name: str = "agent_query"
    description: str = """Query other agents and data sources in the system.
    
    Input should be a JSON string with:
    {
        "target": "DB_AGENT|FILE_MANAGEMENT_AGENT|EXTRACTION_AGENT|STORAGE_AGENT|HDL_AGENT",
        "action": "action_name",
        "data": {"key": "value"},
        "description": "what you're trying to accomplish"
    }
    
    Examples:
    - {"target": "DB_AGENT", "action": "list_entities", "data": {}, "description": "Get all entities"}
    - {"target": "DB_AGENT", "action": "match_entity", "data": {"name": "Trust Stern"}, "description": "Find Trust Stern entity"}
    - {"target": "FILE_MANAGEMENT_AGENT", "action": "scan_files", "data": {}, "description": "Scan Google Drive files"}
    """
    
    settings: Any = None  # Declare as Pydantic field
    agent_coordinator: Any = None  # Will be injected by main.py
    
    def __init__(self):
        super().__init__()
        self.settings = get_settings()
    
    def set_agent_coordinator(self, agent_coordinator):
        """Inject the agent coordinator for internal communication."""
        self.agent_coordinator = agent_coordinator
    
    def _run(self, query: str) -> str:
        """Execute the agent query using internal agent coordinator."""
        try:
            # Parse the JSON input
            try:
                query_data = json.loads(query)
            except json.JSONDecodeError:
                return "Error: Input must be valid JSON. Use format: {'target': 'DB_AGENT', 'action': 'list_entities', 'data': {}, 'description': 'what you want'}"
            
            target = query_data.get("target")
            action = query_data.get("action")
            data = query_data.get("data", {})
            description = query_data.get("description", "Query execution")
            
            if not target or not action:
                return "Error: Both 'target' and 'action' are required"
            
            logger.info(f"AgentQueryTool: {description} - {target}/{action}")
            
            # Use internal agent coordinator instead of HTTP requests
            if self.agent_coordinator:
                return self._query_agent_internal(target, action, data)
            else:
                return "Error: Agent coordinator not available - ensure proper initialization"
                
        except Exception as e:
            logger.error(f"Error in AgentQueryTool: {e}")
            return f"Error executing query: {str(e)}"
    
    def _query_agent(self, target: str, action: str, data: Dict[str, Any]) -> str:
        """Query another agent through the Agent Coordinator."""
        try:
            # Use the /agents/message endpoint to route to other agents
            url = f"{self.base_url}/agents/message"
            payload = {
                "agent_type": target,
                "action": action,
                "data": data
            }
            
            response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get("status") == "success":
                    # Format the response nicely
                    formatted_result = self._format_agent_response(target, action, result.get("result"))
                    return formatted_result
                else:
                    return f"Agent query failed: {result.get('message', 'Unknown error')}"
            else:
                return f"HTTP Error {response.status_code}: {response.text}"
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error querying agent: {e}")
            return f"Network error: Unable to reach {target}. The system may be offline."
        except Exception as e:
            logger.error(f"Error querying agent {target}: {e}")
            return f"Error querying {target}: {str(e)}"
    
    def _query_agent_internal(self, target: str, action: str, data: Dict[str, Any]) -> str:
        """Query another agent through the internal Agent Coordinator (no HTTP)."""
        try:
            # Use internal agent coordinator for direct communication
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Route message through agent coordinator
                result = loop.run_until_complete(
                    self.agent_coordinator.route_message(
                        "AGENT_QUERY_TOOL",
                        target,
                        {
                            "action": action,
                            "data": data
                        }
                    )
                )
                
                if result and result.get("status") == "success":
                    # Format the response nicely
                    formatted_result = self._format_agent_response(target, action, result.get("result"))
                    return formatted_result
                else:
                    return f"Agent {target} returned error: {result.get('message', 'Unknown error') if result else 'No response'}"
                    
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Internal error querying agent: {e}")
            return f"Error communicating with {target}: {str(e)}"
    
    def _query_api_endpoint(self, endpoint: str, data: Dict[str, Any]) -> str:
        """Query a direct API endpoint."""
        try:
            url = f"{self.base_url}{endpoint}"
            
            # Determine HTTP method based on endpoint
            if endpoint.startswith("/chromadb/search"):
                # POST request for vector search
                response = requests.post(url, params=data, timeout=30)
            elif endpoint.startswith("/entities") and not data:
                # GET request for listing entities
                response = requests.get(url, timeout=30)
            elif endpoint.startswith("/entities/match"):
                # POST request for entity matching
                entity_name = data.get("query", data.get("name", ""))
                response = requests.post(f"{url}?entity_name={entity_name}", timeout=30)
            else:
                # Default to GET for most endpoints
                response = requests.get(url, params=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return self._format_api_response(endpoint, result)
            else:
                return f"API Error {response.status_code}: {response.text}"
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error querying API: {e}")
            return f"Network error: Unable to reach API endpoint {endpoint}"
        except Exception as e:
            logger.error(f"Error querying API {endpoint}: {e}")
            return f"Error querying API: {str(e)}"
    
    def _format_agent_response(self, target: str, action: str, result: Any) -> str:
        """Format agent response for better readability."""
        if target == "DB_AGENT":
            if action == "list_entities":
                if isinstance(result, list) and result:
                    entities = []
                    for entity in result:
                        name = entity.get("name", "Unknown")
                        entity_id = entity.get("entity_id", "N/A")
                        category = entity.get("category", "General")
                        entities.append(f"• **{name}** (ID: {entity_id}, Category: {category})")
                    return f"📋 **Found {len(entities)} entities:**\n" + "\n".join(entities)
                elif isinstance(result, list):
                    return "📋 **No entities found in the database.**"
                else:
                    return f"📋 **Database response:** {str(result)}"
            
            elif action == "match_entity":
                if result:
                    name = result.get("name", "Unknown")
                    entity_id = result.get("entity_id", "N/A")
                    category = result.get("category", "General")
                    notes = result.get("notes", "No notes")
                    return f"✅ **Entity Found:**\n• **Name:** {name}\n• **ID:** {entity_id}\n• **Category:** {category}\n• **Notes:** {notes}"
                else:
                    return "❌ **Entity not found in database.**"
            
            elif action == "get_entity":
                if result:
                    return f"✅ **Entity Details:** {json.dumps(result, indent=2)}"
                else:
                    return "❌ **Entity not found.**"
        
        # Default formatting for other agents/actions
        return f"✅ **{target} Response ({action}):**\n{json.dumps(result, indent=2)}"
    
    def _format_api_response(self, endpoint: str, result: Any) -> str:
        """Format API response for better readability."""
        if "/chromadb/search" in endpoint:
            if isinstance(result, dict) and "results" in result:
                results = result["results"]
                if results:
                    formatted = f"🔍 **Found {len(results)} document matches:**\n"
                    for i, doc in enumerate(results[:5], 1):  # Show top 5
                        content = doc.get("content", "No content")[:100] + "..."
                        metadata = doc.get("metadata", {})
                        entity = metadata.get("entity_name", "Unknown entity")
                        formatted += f"{i}. **Entity:** {entity}\n   **Content:** {content}\n"
                    return formatted
                else:
                    return "🔍 **No documents found in vector database.**"
            else:
                return f"🔍 **Vector search result:** {str(result)}"
        
        elif "/entities" in endpoint:
            if isinstance(result, dict) and "result" in result:
                entities = result["result"]
                if isinstance(entities, list) and entities:
                    formatted = f"📋 **Found {len(entities)} entities:**\n"
                    for entity in entities:
                        name = entity.get("name", "Unknown")
                        entity_id = entity.get("entity_id", "N/A")
                        formatted += f"• **{name}** (ID: {entity_id})\n"
                    return formatted
                else:
                    return "📋 **No entities found.**"
        
        # Default formatting
        return f"✅ **API Response ({endpoint}):**\n{json.dumps(result, indent=2)}"
    
    async def _arun(self, query: str) -> str:
        """Async version of the tool."""
        return self._run(query) 