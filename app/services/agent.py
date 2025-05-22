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

def create_agent(include_ocr: bool = True):
    """Create an agent with the specified tools."""
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

def create_agent_old():
    """Create and configure the Gabriel Agent."""
    settings = get_settings()
    
    # Initialize tools
    drive_tool = DriveTool()
    read_sheet_tool = ReadSheetTool()
    write_sheet_tool = WriteSheetTool()
    append_sheet_tool = AppendSheetTool()
    create_sheet_tool = CreateSheetTool()
    # Future Phase: Email functionality
    # email_tool = EmailTool()
    ocr_tool = OCRTool()
    
    tools = [
        drive_tool,
        read_sheet_tool,
        write_sheet_tool,
        append_sheet_tool,
        create_sheet_tool,
        # Future Phase: Email functionality
        # email_tool,
        ocr_tool
    ]
    
    try:
        llm = ChatOpenAI(
            model_name="gpt-4-turbo-preview",
            temperature=0,
            streaming=True,
            openai_api_key=settings.OPENAI_API_KEY
        )
        
        # Create the prompt template with the required agent_scratchpad
        prompt = ChatPromptTemplate.from_messages([
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
        
        agent = create_openai_functions_agent(
            llm=llm,
            tools=tools,
            prompt=prompt
        )
        
        return AgentExecutor.from_agent_and_tools(
            agent=agent,
            tools=tools,
            verbose=True,
            handle_parsing_errors=True
        )
    except Exception as e:
        logger.error(f"Error creating agent: {str(e)}")
        raise 