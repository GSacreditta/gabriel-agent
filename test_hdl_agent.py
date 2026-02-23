#!/usr/bin/env python3
"""
HDL Agent Test - Test review request creation and database persistence
"""

import sys
import os
import asyncio
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_hdl_agent():
    """Test HDL Agent functionality"""
    
    print("\n" + "="*80)
    print("HDL AGENT TEST")
    print("="*80 + "\n")
    
    try:
        # Test 1: Import HDL Agent
        print("Test 1: Importing HDL Agent...")
        from app.agents.hdl_agent import HDLAgent
        hdl_agent = HDLAgent()
        print("✅ HDL Agent imported and created\n")
        
        # Test 2: Import Agent Coordinator
        print("Test 2: Importing Agent Coordinator...")
        from app.agents.agent_coordinator import AgentCoordinator
        coordinator = AgentCoordinator()
        print("✅ Agent Coordinator imported and created\n")
        
        # Test 3: Start Coordinator
        print("Test 3: Starting Agent Coordinator...")
        start_result = await coordinator.start_coordinator()
        if start_result.get("status") == "success":
            print(f"✅ Agent Coordinator started successfully")
            print(f"   Agents initialized: {start_result.get('agents_initialized', [])}\n")
        else:
            print(f"❌ Agent Coordinator failed to start: {start_result}")
            return False
        
        # Test 4: Get HDL Agent instance
        print("Test 4: Getting HDL Agent instance from coordinator...")
        hdl_agent = coordinator.agent_instances.get("HDL_AGENT")
        if hdl_agent:
            print("✅ HDL Agent instance retrieved\n")
        else:
            print("❌ HDL Agent not found in coordinator")
            return False
        
        # Test 5: Check coordinator reference
        print("Test 5: Checking HDL Agent has coordinator reference...")
        if hasattr(hdl_agent, 'coordinator') and hdl_agent.coordinator:
            print("✅ HDL Agent has coordinator reference\n")
        else:
            print("❌ HDL Agent does NOT have coordinator reference!")
            print("   This is why database operations fail!\n")
            return False
        
        # Test 6: Check database service
        print("Test 6: Checking database service...")
        try:
            from app.core.database.service import get_database_service
            db_service = await get_database_service()
            if db_service.is_initialized:
                print("✅ Database service is initialized\n")
            else:
                print("❌ Database service is NOT initialized")
                return False
        except Exception as e:
            print(f"❌ Database service error: {e}\n")
            return False
        
        # Test 7: Check hdl_reviews table
        print("Test 7: Checking hdl_reviews table...")
        try:
            table_check = await db_service.execute_query(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'hdl_reviews')",
                ()
            )
            table_exists = table_check[0][0] if table_check else False
            
            if table_exists:
                print("✅ hdl_reviews table exists\n")
            else:
                print("⚠️  hdl_reviews table does NOT exist")
                print("   Attempting to create it...\n")
                await hdl_agent._ensure_hdl_reviews_table()
                print("✅ hdl_reviews table created\n")
        except Exception as e:
            print(f"❌ Error checking/creating table: {e}\n")
            return False
        
        # Test 8: Create a test review request
        print("Test 8: Creating test review request...")
        try:
            test_request_data = {
                'type': 'test_review',
                'message': 'This is a test review request',
                'entity_name': 'Test Entity'
            }
            
            result = await hdl_agent.request_human_review(
                source_agent="TEST",
                request_data=test_request_data
            )
            
            if result.get('status') == 'success':
                request_id = result.get('request_id')
                print(f"✅ Review request created successfully")
                print(f"   Request ID: {request_id}\n")
                
                # Test 9: Check if it's in memory
                print("Test 9: Checking if request is in memory...")
                if request_id in hdl_agent.pending_reviews:
                    print(f"✅ Request found in memory\n")
                else:
                    print(f"❌ Request NOT found in memory\n")
                    return False
                
                # Test 10: Check if it's in database
                print("Test 10: Checking if request is in database...")
                db_result = await db_service.execute_query(
                    "SELECT request_id, status FROM hdl_reviews WHERE request_id = %s",
                    (request_id,)
                )
                
                if db_result and len(db_result) > 0:
                    print(f"✅ Request found in database!")
                    print(f"   Status: {db_result[0][1]}\n")
                else:
                    print(f"❌ Request NOT found in database!")
                    print(f"   This means _persist_review_to_db() failed silently\n")
                    return False
                
                # Test 11: Simulate restart - restore from database
                print("Test 11: Simulating restart - clearing memory and restoring from database...")
                hdl_agent.pending_reviews.clear()
                print("   Memory cleared")
                
                await hdl_agent.restore_pending_reviews()
                
                if request_id in hdl_agent.pending_reviews:
                    print(f"✅ Request restored from database after 'restart'\n")
                else:
                    print(f"❌ Request NOT restored from database\n")
                    return False
                
                # Test 12: Process human response
                print("Test 12: Testing human response processing...")
                response_data = {
                    'request_id': request_id,
                    'decision': 'approve',
                    'corrections': {},
                    'feedback': 'Test approval'
                }
                
                process_result = await hdl_agent.process_human_response(response_data)
                
                if process_result.get('status') in ['success', 'completed']:
                    print(f"✅ Human response processed successfully\n")
                else:
                    print(f"❌ Human response processing failed: {process_result}\n")
                    return False
                
                print("="*80)
                print("🎉 ALL HDL AGENT TESTS PASSED!")
                print("="*80)
                return True
                
            else:
                print(f"❌ Failed to create review request: {result}")
                return False
                
        except Exception as e:
            print(f"❌ Error creating test review: {e}")
            import traceback
            print(traceback.format_exc())
            return False
        
        # Cleanup
        await coordinator.stop_coordinator()
        
    except Exception as e:
        logger.error(f"❌ HDL Agent test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    result = asyncio.run(test_hdl_agent())
    print(f"\n{'='*80}")
    print(f"FINAL RESULT: {'✅ SUCCESS' if result else '❌ FAILED'}")
    print(f"{'='*80}\n")
    sys.exit(0 if result else 1)
