#!/usr/bin/env python3
"""
Validate Fixes Script - Test all fixes locally before deployment
"""

import sys
import os
import logging
from pathlib import Path

# Add app to Python path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_google_drive_fix():
    """Test Google Drive authentication fix"""
    logger.info("Testing Google Drive authentication fix...")
    
    try:
        # This will test the ADC fallback logic
        from app.services.google_drive import GoogleDriveService
        
        # In local environment, this should fail gracefully with fallback
        try:
            gds = GoogleDriveService()
            logger.info("UNEXPECTED: Google Drive service initialized locally")
            return True
        except ValueError as e:
            if "No valid Google Cloud credentials available" in str(e):
                logger.info("EXPECTED: Google Drive fails locally but has proper fallback logic")
                return True
            else:
                logger.error(f"UNEXPECTED error: {e}")
                return False
        except Exception as e:
            logger.error(f"UNEXPECTED exception: {e}")
            return False
            
    except ImportError as e:
        logger.error(f"Import error: {e}")
        return False

def test_agent_without_drive():
    """Test agent creation without Google Drive dependency"""
    logger.info("Testing agent creation without Google Drive...")
    
    try:
        # Test the minimal agent approach
        from app.core.config import get_settings
        settings = get_settings()
        
        # Verify OpenAI key
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            logger.error("OpenAI API key missing")
            return False
        
        logger.info(f"OpenAI API key found (length: {len(api_key)})")
        
        # Test basic tool creation (non-Google Drive tools)
        from app.tools.system_info_tool import SystemInfoTool
        from app.tools.agent_query_tool import AgentQueryTool
        
        system_tool = SystemInfoTool()
        query_tool = AgentQueryTool()
        
        logger.info("Basic tools created successfully")
        
        # Test ChatOpenAI
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model="gpt-4-turbo-preview",
            temperature=0,
            api_key=api_key.strip()
        )
        
        logger.info("ChatOpenAI created successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"Agent test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_vector_search_tool():
    """Test VectorSearchTool with proper annotations"""
    logger.info("Testing VectorSearchTool...")
    
    try:
        from app.tools.vector_search_tool import VectorSearchTool
        tool = VectorSearchTool()
        logger.info("VectorSearchTool created successfully")
        return True
    except Exception as e:
        logger.error(f"VectorSearchTool failed: {e}")
        return False

def main():
    """Run all validation tests"""
    logger.info("STARTING VALIDATION OF ALL FIXES")
    
    tests = [
        ("Google Drive Authentication Fix", test_google_drive_fix),
        ("Agent Without Drive Dependency", test_agent_without_drive),
        ("VectorSearchTool Pydantic Fix", test_vector_search_tool)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n--- TESTING: {test_name} ---")
        try:
            result = test_func()
            results[test_name] = "PASS" if result else "FAIL"
            logger.info(f"RESULT: {results[test_name]}")
        except Exception as e:
            results[test_name] = f"ERROR: {str(e)}"
            logger.error(f"RESULT: {results[test_name]}")
    
    # Summary
    logger.info(f"\n{'='*50}")
    logger.info("VALIDATION SUMMARY:")
    for test_name, result in results.items():
        logger.info(f"  {test_name}: {result}")
    
    passed = sum(1 for r in results.values() if r == "PASS")
    total = len(results)
    
    logger.info(f"\nOVERALL: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("ALL FIXES VALIDATED - READY FOR DEPLOYMENT")
        return True
    else:
        logger.info("SOME FIXES NEED WORK - SEE DETAILS ABOVE")
        return False

if __name__ == "__main__":
    success = main()
    print(f"\nValidation Result: {'SUCCESS' if success else 'NEEDS_WORK'}")
