from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate, ChatPromptTemplate
from langchain.prompts.chat import SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import Dict, Optional
import logging
from ..core.config import get_settings
# Future Phase: Email functionality
# from ..tools.email_tool import EmailTool
from ..tools.drive_tool import DriveTool
from ..tools.sheets_tool import ReadSheetTool, WriteSheetTool, AppendSheetTool, CreateSheetTool
from ..tools.ocr_tool import OCRTool

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
        self.agent_executor = create_langchain_agent(include_ocr=True)
        
    async def process_message(self, message: str) -> str:
        """Process an incoming message and generate a response.
        
        Args:
            message (str): The incoming message to process
            
        Returns:
            str: The generated response
        """
        try:
            # Use the LangChain agent to process the message
            response = await self.agent_executor.ainvoke({"input": message})
            return response.get("output", "I'm not sure how to respond to that.")
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            return "I encountered an error while processing your message. Please try again."

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

def create_langchain_agent(include_ocr: bool = True):
    """Create a LangChain agent with the specified tools."""
    tools = []
    
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
                model_name="gpt-4-turbo-preview",
                temperature=0,
                streaming=True,
                openai_api_key=get_settings().OPENAI_API_KEY
            ),
            tools=tools,
            prompt=ChatPromptTemplate.from_messages([
                ("system", """You are Gabriel, an AI assistant designed to process documents from Google Drive, read and extract information and plan tasks. 
                You have access to various tools to help with document processing, including:
                - Drive operations (list, search, download)
                - Sheet operations (read, write, append, create)
                - PDF and OCR capabilities for text extraction
                - Vector Database for storing and searching documents
                Your main responsibilities are:
                1. Scan Google Drive Master folder for new documents (Every 30 minutes)
                2. Identify file format and metadata (PDF, images, Google Docs, spreadsheets)
                3. Process documents, by reading and extracting(embedding, chunking, etc.) structured information
                4. Extract and read key information with confidence scores
                5. Prepare results for human review according to required fields in "Structured output for document information."
                6. Plan tasks for human review and action
                7. Identify "similar entity Sub-Folder name" by searching Google Drive Master folder for similar entity names
                8. Move document to "similar entity Sub-Folder", if not found, create new "similar entity Sub-Folder" (ask human for confirmation)
                9. Move document  to "entity Sub-Folder" with processed document
                10. Store processed document in Vector Database
            
                Always provide clear, structured responses and use the available tools effectively."""),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad")
            ])
        ),
        tools=tools,
        verbose=True,
        handle_parsing_errors=True
    )

def create_agent() -> Agent:
    """Create and return a new agent instance."""
    return Agent() 
