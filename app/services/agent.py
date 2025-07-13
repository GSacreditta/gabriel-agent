from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.prompts.chat import MessagesPlaceholder
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import Dict, Optional, Any
import logging
from ..core.config import get_settings
# Future Phase: Email functionality
# from ..tools.email_tool import EmailTool
from ..tools.drive_tool import DriveTool
from ..tools.sheets_tool import ReadSheetTool, WriteSheetTool, AppendSheetTool, CreateSheetTool
from ..tools.ocr_tool import OCRTool
from ..tools.system_info_tool import SystemInfoTool
from ..tools.agent_query_tool import AgentQueryTool
import traceback

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class DocumentInfo(BaseModel):
    """Structured output for document information."""
    entity_name: str = Field(description="Full legal name of entity")
    issue_date: str = Field(description="Date in YYYY-MM-DD format")
    subject: str = Field(description="Main topic/purpose of the document")
    summary: str = Field(description="Two-line summary of key points")
    document_type: str = Field(description="Type of document")
    drive_link: str = Field(description="Google Drive URL")
    confidence_scores: Dict[str, float] = Field(
        description="Confidence scores for each extraction",
        default_factory=lambda: {
            "entity_detection": 0.0,
            "date_extraction": 0.0,
            "topic_identification": 0.0
        }
    )

class Agent:
    """Main agent class for processing messages and generating responses."""
    
    def __init__(self):
        """Initialize the agent with necessary configurations."""
        self.settings = get_settings()
        logger.info("Creating LangChain agent...")
        self.agent_executor = create_langchain_agent(include_ocr=True)
        logger.info("LangChain agent created successfully")
        
    def process_message_sync(self, message: str) -> str:
        """Process an incoming message synchronously.
        
        This method is used by the Slack socket mode handlers which run in a callback
        and cannot use async/await.
        
        Args:
            message (str): The incoming message to process
            
        Returns:
            str: The generated response
        """
        try:
            logger.info(f"Processing message synchronously: {message}")
            
            # Use the LangChain agent to process the message
            response = self.agent_executor.invoke({"input": message})
            
            # Extract the response text
            if isinstance(response, dict) and "output" in response:
                return response["output"]
            elif isinstance(response, str):
                return response
            else:
                logger.warning(f"Unexpected response format: {type(response)}")
                return str(response)
                
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            logger.error(f"Traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")
            return "I encountered an error while processing your message."
        
    async def process_message(self, message: str) -> str:
        """Process an incoming message and generate a response.
        
        Args:
            message (str): The incoming message to process
            
        Returns:
            str: The generated response
        """
        try:
            logger.info(f"Processing message: {message}")
            
            # Use the LangChain agent to process the message
            response = await self.agent_executor.ainvoke({"input": message})
            
            # Extract the response text
            if isinstance(response, dict) and "output" in response:
                return response["output"]
            elif isinstance(response, str):
                return response
            else:
                logger.warning(f"Unexpected response format: {type(response)}")
                return str(response)
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            logger.error(f"Traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")
            return "I encountered an error while processing your message."

    async def plan_review_tasks(self, document_info: dict) -> list:
        """Plan tasks for human review based on document information.
        
        Args:
            document_info (dict): Information about the processed document
            
        Returns:
            list: List of tasks that need human review
        """
        try:
            # Validate required fields
            required_fields = ['file_name', 'entity_name', 'processing_time', 'ocr_result']
            missing_fields = [field for field in required_fields if field not in document_info]
            if missing_fields:
                logger.error(f"Missing required fields in document_info: {missing_fields}")
                return ["Error: Missing required document information"]

            # Extract information with validation
            file_name = document_info.get('file_name', 'Unknown file')
            entity_name = document_info.get('entity_name', 'Unknown entity')
            processing_time = document_info.get('processing_time', 'Unknown time')
            
            # Get OCR results with validation
            ocr_result = document_info.get('ocr_result', {})
            confidence_scores = ocr_result.get('data', {}).get('confidence_scores', {})
            
            # Prepare input for the agent
            input_text = f"""Based on the following document information, create a list of tasks that need human review:
            Document Name: {file_name}
            Entity Name: {entity_name}
            Processing Time: {processing_time}
            Confidence Scores: {confidence_scores}
            
            Please provide a list of specific tasks that require human review, such as:
            - Verifying extracted information
            - Confirming entity name
            - Reviewing document classification
            - Checking confidence scores
            """
            
            # Get agent's response
            response = await self.agent_executor.ainvoke({"input": input_text})
            
            # Parse the response into a list of tasks
            tasks = response.get("output", "").split("\n")
            tasks = [task.strip() for task in tasks if task.strip()]
            
            # Add default tasks if none were generated
            if not tasks:
                tasks = [
                    f"Review entity name: {entity_name}",
                    "Verify document classification",
                    "Check extracted information accuracy"
                ]
            
            return tasks
            
        except Exception as e:
            logger.error(f"Error planning review tasks: {str(e)}")
            return ["Error planning review tasks. Please check the logs."]

    async def generate_summary(self, text: str, prompt: str) -> str:
        """Generate a summary of the document text.
        
        Args:
            text (str): The document text to summarize
            prompt (str): Specific instructions for the summary
            
        Returns:
            str: The generated summary
        """
        try:
            # Prepare input for the agent
            input_text = f"""Please summarize the following text according to these instructions:
            {prompt}
            
            Text to summarize:
            {text[:2000]}  # Limit text to first 2000 chars for summary
            """
            
            # Get agent's response
            response = await self.agent_executor.ainvoke({"input": input_text})
            
            # Extract and validate summary
            summary = response.get("output", "").strip()
            if not summary:
                return "Summary generation failed"
                
            return summary
            
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return "Summary generation failed"

    async def process_text(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Mock processing text.
        
        Args:
            text: Text to process
            context: Optional processing context
            
        Returns:
            Dict containing mock response
        """
        logger.info(f"MOCK AGENT - Processing text: {text[:100]}...")
        return {
            "success": True,
            "processed_text": text,
            "context": context or {}
        }

    async def get_file_metadata(self, file_id: str) -> Dict[str, Any]:
        logger.info(f"MOCK DRIVE - Getting metadata for {file_id}")
        return {
            "id": file_id,
            "name": "test_file.txt",
            "mimeType": "text/plain"
        }

def create_langchain_agent(include_ocr: bool = True):
    """Create a LangChain agent with the specified tools."""
    tools = []
    
    # Add system awareness tools first (most important)
    try:
        system_info_tool = SystemInfoTool()
        tools.append(system_info_tool)
    except Exception as e:
        logger.warning(f"Failed to initialize SystemInfo tool: {str(e)}")
    
    try:
        agent_query_tool = AgentQueryTool()
        tools.append(agent_query_tool)
    except Exception as e:
        logger.warning(f"Failed to initialize AgentQuery tool: {str(e)}")
    
    # Add OCR tool only if requested
    if include_ocr:
        try:
            ocr_tool = OCRTool()
            tools.append(ocr_tool)
        except Exception as e:
            logger.warning(f"Failed to initialize OCR tool: {str(e)}")
    
    # Add other tools
    try:
        drive_tool = DriveTool()
        tools.append(drive_tool)
    except Exception as e:
        logger.warning(f"Failed to initialize Drive tool: {str(e)}")
    
    # Create and return the agent
    return AgentExecutor.from_agent_and_tools(
        agent=create_openai_functions_agent(
            llm=ChatOpenAI(
                model="gpt-4-turbo-preview",
                temperature=0,
                api_key=get_settings().OPENAI_API_KEY
            ),
            tools=tools,
            prompt=ChatPromptTemplate.from_messages([
                ("system", """You are Gabriel, an intelligent AI assistant with access to a comprehensive multi-agent system for document processing and entity management.

🧠 **SYSTEM AWARENESS**: Before answering ANY question, you should understand your capabilities:
- Use the 'system_info' tool to learn about available data sources and tools
- Use 'agent_query' tool to access other agents and databases
- ALWAYS check multiple data sources before concluding something doesn't exist

🔍 **QUERY STRATEGY**: When users ask about entities, documents, or data:
1. **First**: Query the database using agent_query (most reliable source)
2. **Second**: Search vector database for related documents  
3. **Third**: Check Google Drive for files/folders
4. **Always**: Explain which sources you checked and provide comprehensive answers

📊 **AVAILABLE DATA SOURCES**:
- **PostgreSQL Database**: Primary entity storage (use DB_AGENT)
- **ChromaDB Vector Database**: Document content and semantic search
- **Google Drive**: File storage and organization
- **Google Sheets**: Structured data processing

🤖 **CORE RESPONSIBILITIES**:
1. Entity management and search across all data sources
2. Document processing with OCR and text extraction
3. Human review workflow coordination
4. File organization and storage management
5. Task planning and execution
6. Multi-source data correlation and analysis

⚡ **INTERACTION GUIDELINES**:
- Be proactive in checking ALL relevant data sources
- Provide specific, actionable information
- Explain your search process and data sources checked  
- If information is missing, suggest next steps or alternatives
- Use tools effectively to give comprehensive answers
- Never assume data doesn't exist without checking all sources

🛠️ **KEY TOOLS**:
- system_info: Learn about capabilities and data sources
- agent_query: Query other agents (DB_AGENT, etc.) and APIs
- drive operations, OCR, sheet tools for document processing

Remember: You have access to a powerful multi-agent system. Use it!"""),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad")
            ])
        ),
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=3  # Limit iterations to prevent infinite loops
    )

def create_agent() -> Agent:
    """Create and return a new agent instance."""
    return Agent() 
