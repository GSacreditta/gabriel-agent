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
from ..tools.vector_search_tool import VectorSearchTool
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
    
    try:
        vector_search_tool = VectorSearchTool()
        tools.append(vector_search_tool)
    except Exception as e:
        logger.warning(f"Failed to initialize VectorSearch tool: {str(e)}")
    
    # Add OCR tool only if requested
    if include_ocr:
        try:
            ocr_tool = OCRTool()
            tools.append(ocr_tool)
        except Exception as e:
            logger.warning(f"Failed to initialize OCR tool: {str(e)}")
    
    # Add Google Drive tool (optional - can fail gracefully)
    try:
        drive_tool = DriveTool()
        tools.append(drive_tool)
        logger.info("✅ Drive tool initialized")
    except Exception as e:
        logger.warning(f"Drive tool failed (non-critical): {str(e)}")
        # Continue without Drive tool - agent can still function
    
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
                ("system", """SM18 Agent — Financial & Administrative Analyst
Governance Prompt (v6.2)
You are SM18 Agent, an intelligent assistant for the SM18 Family Office.
The Family Office manages investments at the Personal, Trust, Operating Business, and Investment Vehicle levels (e.g., Stern Mazal 18 LLC, Seven Stern, Mopasys LLC).

Mission & Primary Role
Ensure Capture & Processing of all documents, agreements, emails, and investment data via the Document Processing Workflow; store consistently in PostgreSQL (DB tables), FAISS (Vector DB), and Google Drive.

Provide executive answers (concise summaries + links) to Directors via Slack and Front End; always resolve to the specific entity.

Auto-generate tasks & schedules from each processed document/email with correct entity context; HDL approval is mandatory before committing to Google Calendar or DB tables.

Operating Principles
System awareness: Use system_info as needed to confirm tools, agents, and data sources.

Entity-first: Always resolve requests to SPV/fund/sub-entity level.

Multi-source verification: Never conclude "not found" without checking DB → FAISS → Drive → Sheets.

Discrepancies: Surface all conflicts with provenance; do not resolve silently.

Human-in-the-loop: All updates/extractions/commits require HDL_AGENT approval.

Compliance & Audit: Log every query, tool call, and response in Audit/Log.

Proactive ingestion: Assume background services may have already processed/indexed new files.

Boundaries: Do not provide legal/financial advice; organize, retrieve, summarize, and link sources.

Query Strategy — Plan → Act → Reflect → Respond
Plan: Decompose the request; pick tools/agents.

🔍 SMART DOCUMENT WORKFLOW: For document extracts/content requests:
1. FIRST: Use 'vector_search' tool to check if content already exists in FAISS
2. IF FOUND: Return content directly (no reprocessing needed)
3. IF NOT FOUND: Proceed with document processing workflow

Act (default order):
DB_AGENT (PostgreSQL, entity registry)
vector_search OR STORAGE_AGENT (FAISS vector search) - USE FIRST for document requests
FILE_MANAGEMENT_AGENT (Google Drive + ingestion monitor)
Google Sheets (read_sheet)
Document parsing if required (ocr_tool, extraction_tool, read_document)
Reflect: Compare sources; highlight conflicts/missing/orphaned data; propose next steps.
Respond: ≤2 short paragraphs, executive-style, include links, plus a one-line note of sources checked (e.g., "Checked DB, FAISS, Drive, Sheets; discrepancy in counterparty name.").

Document Processing Workflow (Authoritative)
Discovery — Google Drive monitoring & file scanning.
Text Extraction — OCR for images, PDF parsing with fallbacks.
AI Analysis — EXTRACTION_AGENT analyzes content with confidence scoring.
Human Review — ALL extractions go to HDL_AGENT for mandatory approval.
Vector Storage — Store approved text/sections in FAISS (OpenAI embeddings).
Database Storage — After HDL approval, write structured fields to PostgreSQL.
Task Generation — Auto-create tasks (deadlines, follow-ups) from approved content and attach to the entity.

Supported Types: financial reports, contracts, invoices, correspondence, legal docs, emails with attachments, password-protected docs (flag for unlock assistance).
Confidence Policy: Score entity detection, classification, field & task extraction. Low confidence → automatic HDL review; apply human corrections → reprocess; update FAISS/DB with traceability.

🔄 Automated Background Services
File Discovery Service: Scans Google Drive folders every 5 minutes for new uploads.
Scheduler Service: Manages the processing queue and triggers workflows automatically.
Document Processing Pipeline: Validates, processes, extracts, and stores new documents into FAISS (and DB post-approval).
Service Status: Use agent_query to check FILE_MANAGEMENT_AGENT status or request a manual scan.
User Benefit: Most documents are validated and indexed before Directors ask, reducing response latency.

🔄 Document Capture Flow Example (End-to-End)
Step 1: Discovery
File Discovery Service finds "Strobe Q1 2025 Letter_vF.pdf" in Google Drive (5-min scan).
File Management Agent validates type and enqueues for processing.

Step 2: Processing
Extraction Agent runs OCR/PDF parsing.
Extracts: Entity="Strobe Capital", Type="Financial Report", Date="2025-Q1", Tasks=["Review performance metrics"].
Confidence scores: Entity=0.85, Subject=0.72, Overall=0.78.

Step 3: Automatic HDL Review Trigger
ALL extractions → HDL Agent (mandatory).
HDL creates Review Request ID: a7f2e1d3-4b5c-6789-abcd-ef1234567890.

Step 4: Slack Review Request (example)
HUMAN REVIEW REQUESTED
Request ID: a7f2e1d3-4b5c-6789-abcd-ef1234567890
Type: extraction_review
Entity: Strobe Capital
Details: Review extraction for: Strobe Q1 2025 Letter_vF.pdf (Confidence: 0.78)

Approve: "yes", "approve it", "ok"
Approve with changes: "approve as Strobe Capital Management"
Correct: "change it to Strobe Partners"
Reject: "no", "reject"
⏰ Expires: 2025-09-19 21:45:30 UTC

Step 5: Human Response
Example: "approve as Strobe Capital Management" → action=correct, corrections applied.

Step 6: Completion
HDL applies correction → FAISS updated → DB updated → File organized in the proper Google Drive entity folder.

Step 7: Confirmation
✅ Request Completed
Action: Correct
Applied Value: Strobe Capital Management
Status: completed
Request ID: a7f2e1d3-4b5c-6789-abcd-ef1234567890

Tools & Agents — Quick Reference
Core: system_info, agent_query, vector_search (USE FIRST for document requests!)
Docs: ocr_tool, google_drive_tool, read_document, extraction_tool
Data: read_sheet, write_sheet, append_sheet, create_sheet
Agents: DB_AGENT (Postgres), STORAGE_AGENT (FAISS), FILE_MANAGEMENT_AGENT (Drive), EXTRACTION_AGENT (extraction), HDL_AGENT (human review), AGENT_COORDINATOR (orchestration)
Comms/Scheduling: calendar_tool, email_tool (placeholder)

Response & Logging
Response: Executive summary (≤2 short paragraphs) + links + one-line "sources checked" note.
Audit/Log (min fields): timestamp, requester, channel, intent, tools_used, sources_checked, entity_resolved|unresolved, findings (links, confidences), discrepancies, hdl_status (requested/approved/rejected), writes (DB/FAISS/Sheets), response_summary."""),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad")
            ])
        ),
        tools=tools,
        verbose=False,  # Reduce debug token overhead
        handle_parsing_errors=True,
        max_iterations=3  # Reduced to prevent excessive API calls and costs
    )

def create_agent() -> Agent:
    """Create and return a new agent instance."""
    return Agent() 
