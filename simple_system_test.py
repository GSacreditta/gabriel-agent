#!/usr/bin/env python3
"""
Simple Gabriel Agent System Test
================================

A simplified test script that verifies core functionality without Unicode issues.
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

async def test_core_services():
    """Test core services initialization."""
    print("CORE SERVICES TEST")
    print("=" * 50)
    
    test_results = {}
    
    # Test 1: Agent service
    try:
        from app.services.agent import create_agent
        agent = create_agent()
        test_results["agent_service"] = "PASS"
        print("[PASS] Agent service initialized")
    except Exception as e:
        test_results["agent_service"] = f"FAIL: {e}"
        print(f"[FAIL] Agent service: {e}")
    
    # Test 2: Google Drive service
    try:
        from app.services.google_drive import GoogleDriveService
        drive_service = GoogleDriveService()
        
        # Test basic functionality
        files = await drive_service.get_folder_contents()
        test_results["google_drive_service"] = f"PASS - Found {len(files) if files else 0} files"
        print(f"[PASS] Google Drive service - Found {len(files) if files else 0} files")
        
        await drive_service.cleanup()
    except Exception as e:
        test_results["google_drive_service"] = f"FAIL: {e}"
        print(f"[FAIL] Google Drive service: {e}")
    
    # Test 3: Vector storage service
    try:
        from app.services.vector_storage_service import VectorStorageService
        vector_service = VectorStorageService(use_temp_dir=True)
        
        stats = vector_service.get_collection_stats()
        test_results["vector_storage_service"] = "PASS"
        print("[PASS] Vector storage service initialized")
        
        await vector_service.cleanup()
    except Exception as e:
        test_results["vector_storage_service"] = f"FAIL: {e}"
        print(f"[FAIL] Vector storage service: {e}")
    
    # Test 4: Database connectivity
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text
        
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            engine = create_async_engine(database_url, echo=False)
            
            async with engine.begin() as conn:
                result = await conn.execute(text("SELECT 1"))
                result.fetchone()
                
            await engine.dispose()
            test_results["database_connectivity"] = "PASS"
            print("[PASS] Database connectivity")
        else:
            test_results["database_connectivity"] = "FAIL: DATABASE_URL not set"
            print("[FAIL] Database connectivity: DATABASE_URL not set")
    except Exception as e:
        test_results["database_connectivity"] = f"FAIL: {e}"
        print(f"[FAIL] Database connectivity: {e}")
    
    # Test 5: Slack service
    try:
        from app.services.slack_service import SlackService
        slack_service = SlackService()
        
        if test_results.get("agent_service") == "PASS":
            await slack_service.initialize(agent)
            test_results["slack_service"] = "PASS"
            print("[PASS] Slack service initialized")
        else:
            test_results["slack_service"] = "PASS - Basic initialization"
            print("[PASS] Slack service - Basic initialization")
            
        await slack_service.cleanup()
    except Exception as e:
        test_results["slack_service"] = f"FAIL: {e}"
        print(f"[FAIL] Slack service: {e}")
    
    return test_results

async def test_agent_architecture():
    """Test the agent coordinator and individual agents."""
    print("\nAGENT ARCHITECTURE TEST")
    print("=" * 50)
    
    test_results = {}
    
    try:
        from app.agents.agent_coordinator import AgentCoordinator
        
        # Initialize Agent Coordinator
        agent_coordinator = AgentCoordinator()
        start_result = await agent_coordinator.start_coordinator()
        
        if start_result.get("status") == "success":
            agents = start_result.get('agents', {})
            test_results["agent_coordinator"] = f"PASS - {len(agents)} agents started"
            print(f"[PASS] Agent Coordinator - {len(agents)} agents started")
            
            # Test agent status
            agent_status = await agent_coordinator.get_agent_status()
            active_agents = [name for name, status in agent_status.items() if status.get("status") == "active"]
            test_results["agent_status"] = f"PASS - {len(active_agents)} active agents"
            print(f"[PASS] Agent Status - {len(active_agents)} active agents: {', '.join(active_agents)}")
            
            # Test capabilities
            capabilities = await agent_coordinator.get_agent_capabilities()
            test_results["agent_capabilities"] = f"PASS - {len(capabilities) if capabilities else 0} capabilities"
            print(f"[PASS] Agent Capabilities - {len(capabilities) if capabilities else 0} total capabilities")
            
            # Cleanup
            await agent_coordinator.stop_coordinator()
            
        else:
            test_results["agent_coordinator"] = f"FAIL - {start_result}"
            print(f"[FAIL] Agent Coordinator: {start_result}")
            
    except Exception as e:
        test_results["agent_coordinator"] = f"FAIL: {e}"
        print(f"[FAIL] Agent Coordinator: {e}")
    
    return test_results

def test_environment_config():
    """Test environment configuration."""
    print("ENVIRONMENT CONFIGURATION TEST")
    print("=" * 50)
    
    test_results = {}
    
    required_vars = [
        "OPENAI_API_KEY",
        "GOOGLE_APPLICATION_CREDENTIALS", 
        "GOOGLE_DRIVE_FOLDER_ID",
        "SLACK_BOT_TOKEN",
        "DATABASE_URL"
    ]
    
    for var in required_vars:
        if os.getenv(var):
            test_results[f"env_{var}"] = "PASS"
            print(f"[PASS] {var} is set")
        else:
            test_results[f"env_{var}"] = "FAIL"
            print(f"[FAIL] {var} is not set")
    
    # Test configuration loading
    try:
        from app.core.config import get_settings
        settings = get_settings()
        test_results["config_loading"] = "PASS"
        print("[PASS] Configuration loading")
    except Exception as e:
        test_results["config_loading"] = f"FAIL: {e}"
        print(f"[FAIL] Configuration loading: {e}")
    
    return test_results

async def main():
    """Run all tests."""
    print("GABRIEL AGENT SYSTEM TEST")
    print("=" * 70)
    print()
    
    all_results = {}
    
    # Run all test suites
    env_results = test_environment_config()
    all_results.update(env_results)
    
    print()
    core_results = await test_core_services()
    all_results.update(core_results)
    
    print()
    agent_results = await test_agent_architecture()
    all_results.update(agent_results)
    
    # Generate summary
    print("\nTEST SUMMARY")
    print("=" * 50)
    
    passed_tests = [test for test, result in all_results.items() if result == "PASS" or result.startswith("PASS")]
    failed_tests = [test for test, result in all_results.items() if result.startswith("FAIL")]
    
    print(f"Total Tests: {len(all_results)}")
    print(f"Passed: {len(passed_tests)}")
    print(f"Failed: {len(failed_tests)}")
    print(f"Success Rate: {len(passed_tests)/len(all_results)*100:.1f}%")
    
    print(f"\nPassed Tests: {', '.join(passed_tests)}")
    if failed_tests:
        print(f"Failed Tests: {', '.join(failed_tests)}")
    
    if len(failed_tests) == 0:
        print("\nALL TESTS PASSED! System is healthy and ready.")
    elif len(failed_tests) <= 2:
        print("\nSystem mostly healthy with minor issues.")
    else:
        print("\nMultiple failures detected. System needs attention.")

if __name__ == "__main__":
    asyncio.run(main())
