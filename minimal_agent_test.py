#!/usr/bin/env python3
"""
Minimal Agent Test - Test agent creation without Google Drive dependency
"""

import sys
import os
import asyncio
import logging
from pathlib import Path

# Add app to Python path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_minimal_agent():
    """Test agent creation with minimal dependencies"""
    
    try:
        logger.info("Testing minimal agent creation...")
        
        # Test 1: Basic imports
        from app.core.config import get_settings
        settings = get_settings()
        logger.info("✅ Settings loaded")
        
        # Test 2: OpenAI API key
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OPENAI_API_KEY missing")
        logger.info(f"✅ OpenAI API key found (length: {len(api_key)})")
        
        # Test 3: Basic tool creation (without Google Drive)
        from app.tools.system_info_tool import SystemInfoTool
        system_tool = SystemInfoTool()
        logger.info("✅ SystemInfoTool created")
        
        # Test 4: ChatOpenAI creation
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model="gpt-4-turbo-preview",
            temperature=0,
            api_key=api_key.strip()  # Strip any whitespace
        )
        logger.info("✅ ChatOpenAI created")
        
        # Test 5: Prompt creation
        from langchain.prompts import ChatPromptTemplate
        from langchain_core.prompts.chat import MessagesPlaceholder
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are SM18 Agent, a test assistant."),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])
        logger.info("✅ Prompt created")
        
        # Test 6: Agent creation
        from langchain.agents import create_openai_functions_agent, AgentExecutor
        
        agent = create_openai_functions_agent(
            llm=llm,
            tools=[system_tool],
            prompt=prompt
        )
        logger.info("✅ OpenAI functions agent created")
        
        agent_executor = AgentExecutor.from_agent_and_tools(
            agent=agent,
            tools=[system_tool],
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=10
        )
        logger.info("✅ Agent executor created")
        
        # Test 7: Simple message processing
        response = await agent_executor.ainvoke({"input": "Hello, test message"})
        logger.info(f"✅ Agent response: {response.get('output', 'No output')[:100]}...")
        
        logger.info("🎉 MINIMAL AGENT TEST SUCCESSFUL")
        return True
        
    except Exception as e:
        logger.error(f"❌ Minimal agent test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    result = asyncio.run(test_minimal_agent())
    print(f"\nTest Result: {'SUCCESS' if result else 'FAILED'}")
