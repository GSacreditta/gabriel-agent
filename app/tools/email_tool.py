from langchain.tools import BaseTool
from typing import Optional, Type, Dict, Any, List
from langchain_core.pydantic_v1 import BaseModel, Field

class EmailToolInput(BaseModel):
    """Input for email tool."""
    action: str = Field(..., description="The action to perform (send, read, etc.)")
    recipient: Optional[str] = Field(None, description="Email recipient")
    subject: Optional[str] = Field(None, description="Email subject")
    body: Optional[str] = Field(None, description="Email body")
    attachments: Optional[List[str]] = Field(None, description="List of attachment paths")

class EmailTool(BaseTool):
    """Tool for managing emails."""
    
    name: str = Field(default="email_tool", description="The unique name of the tool that clearly communicates its purpose.")
    description: str = Field(default="""Use this tool to manage emails.
    This tool can:
    1. Send emails
    2. Read emails
    3. Manage email attachments
    
    Input should be a JSON string with the following format:
    {
        "action": "send" or "read",
        "recipient": "email@example.com",
        "subject": "Email subject",
        "body": "Email body",
        "attachments": ["path/to/file1", "path/to/file2"]
    }
    """, description="Used to tell the model how/when/why to use the tool.")
    args_schema: Type[BaseModel] = EmailToolInput
    
    async def _arun(self, **kwargs) -> str:
        """
        Run the email tool asynchronously.
        
        Args:
            **kwargs: The input parameters
            
        Returns:
            str: The result of the email operation
        """
        try:
            action = kwargs.get("action")
            if action == "send":
                return "Email sending functionality will be implemented soon."
            elif action == "read":
                return "Email reading functionality will be implemented soon."
            else:
                raise ValueError(f"Invalid action: {action}")
        except Exception as e:
            return f"Error: {str(e)}"
    
    def _run(self, **kwargs) -> str:
        """
        Run the email tool synchronously.
        This is a fallback method that should not be used.
        
        Args:
            **kwargs: The input parameters
            
        Returns:
            str: The result of the email operation
        """
        raise NotImplementedError("Email tool does not support synchronous execution") 