"""
Debug script for HDL review request ID: e604366c-6712-4d40-8eab-685d835dd1fe

This script checks:
1. Database connectivity
2. hdl_reviews table existence
3. Whether the specific request exists in the database
4. Recent requests in the system
"""

import asyncio
import os
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main diagnostic function"""
    
    REQUEST_ID = "e604366c-6712-4d40-8eab-685d835dd1fe"
    
    print("\n" + "="*80)
    print("HDL REQUEST DEBUGGING REPORT")
    print(f"Request ID: {REQUEST_ID}")
    print("="*80 + "\n")
    
    # Step 1: Check database service
    print("Step 1: Checking database service...")
    try:
        from app.core.database.service import get_database_service
        
        db_service = await get_database_service()
        
        if not db_service.is_initialized:
            print("❌ ERROR: Database service is not initialized!")
            print("   The application cannot connect to the database.")
            print("   Check your database credentials and connection settings.")
            return
        
        print("✅ Database service is initialized and connected")
        
    except Exception as e:
        print(f"❌ ERROR: Failed to initialize database service: {e}")
        import traceback
        print(traceback.format_exc())
        return
    
    # Step 2: Check if hdl_reviews table exists
    print("\nStep 2: Checking if hdl_reviews table exists...")
    try:
        result = await db_service.execute_query(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'hdl_reviews'
            )
            """,
            ()
        )
        
        table_exists = result[0][0] if result else False
        
        if table_exists:
            print("✅ hdl_reviews table exists")
        else:
            print("❌ ERROR: hdl_reviews table does NOT exist!")
            print("   The table needs to be created.")
            print("   Creating table now...")
            
            # Try to create the table
            await db_service.execute_command(
                """
                CREATE TABLE IF NOT EXISTS hdl_reviews (
                    request_id VARCHAR(255) PRIMARY KEY,
                    source_agent VARCHAR(100) NOT NULL,
                    request_type VARCHAR(100),
                    data TEXT,
                    message TEXT,
                    status VARCHAR(50),
                    created_at TIMESTAMP,
                    expires_at TIMESTAMP
                )
                """,
                ()
            )
            print("✅ Table created successfully")
            
    except Exception as e:
        print(f"❌ ERROR checking/creating hdl_reviews table: {e}")
        import traceback
        print(traceback.format_exc())
        return
    
    # Step 3: Search for the specific request ID
    print(f"\nStep 3: Searching for request ID {REQUEST_ID}...")
    try:
        result = await db_service.execute_query(
            """
            SELECT request_id, source_agent, request_type, message, 
                   status, created_at, expires_at
            FROM hdl_reviews 
            WHERE request_id = %s
            """,
            (REQUEST_ID,)
        )
        
        if result:
            print("✅ Request found in database!")
            row = result[0]
            print(f"   Request ID: {row[0]}")
            print(f"   Source Agent: {row[1]}")
            print(f"   Request Type: {row[2]}")
            print(f"   Message: {row[3][:100]}..." if len(str(row[3])) > 100 else f"   Message: {row[3]}")
            print(f"   Status: {row[4]}")
            print(f"   Created At: {row[5]}")
            print(f"   Expires At: {row[6]}")
            
            # Check if expired
            from datetime import datetime
            if row[6] and datetime.utcnow() > row[6]:
                print("\n⚠️  WARNING: This request has EXPIRED!")
                print(f"   Expired at: {row[6]}")
                print(f"   Current time: {datetime.utcnow()}")
        else:
            print("❌ Request NOT found in database!")
            print("   Possible reasons:")
            print("   1. The request was never created (failed to save)")
            print("   2. The request was deleted after processing")
            print("   3. The request ID is incorrect")
            print("   4. The application instance that created it has restarted")
            
    except Exception as e:
        print(f"❌ ERROR searching for request: {e}")
        import traceback
        print(traceback.format_exc())
    
    # Step 4: Show recent requests
    print("\nStep 4: Showing recent HDL review requests...")
    try:
        result = await db_service.execute_query(
            """
            SELECT request_id, source_agent, request_type, status, 
                   created_at, expires_at
            FROM hdl_reviews 
            ORDER BY created_at DESC
            LIMIT 10
            """,
            ()
        )
        
        if result:
            print(f"✅ Found {len(result)} recent request(s):")
            for i, row in enumerate(result, 1):
                print(f"\n   {i}. Request ID: {row[0]}")
                print(f"      Source: {row[1]}")
                print(f"      Type: {row[2]}")
                print(f"      Status: {row[3]}")
                print(f"      Created: {row[4]}")
                print(f"      Expires: {row[5]}")
        else:
            print("⚠️  No requests found in database")
            print("   This suggests:")
            print("   1. No HDL reviews have been created yet")
            print("   2. The table was recently created/cleared")
            print("   3. Reviews are not being persisted to the database")
            
    except Exception as e:
        print(f"❌ ERROR fetching recent requests: {e}")
        import traceback
        print(traceback.format_exc())
    
    # Step 5: Check agent coordinator status
    print("\nStep 5: Checking Agent Coordinator status...")
    try:
        from app.main import services
        
        if services.get("agent_coordinator"):
            coordinator = services["agent_coordinator"]
            print("✅ Agent Coordinator is initialized")
            
            # Check if HDL Agent is running
            if hasattr(coordinator, 'agent_instances'):
                hdl_agent = coordinator.agent_instances.get("HDL_AGENT")
                if hdl_agent:
                    print("✅ HDL Agent is running")
                    
                    # Check in-memory reviews
                    if hasattr(hdl_agent, 'pending_reviews'):
                        pending_count = len(hdl_agent.pending_reviews)
                        completed_count = len(hdl_agent.completed_reviews) if hasattr(hdl_agent, 'completed_reviews') else 0
                        
                        print(f"   Pending reviews in memory: {pending_count}")
                        print(f"   Completed reviews in memory: {completed_count}")
                        
                        if REQUEST_ID in hdl_agent.pending_reviews:
                            print(f"✅ Request {REQUEST_ID} found in pending reviews (memory)")
                        elif hasattr(hdl_agent, 'completed_reviews') and REQUEST_ID in hdl_agent.completed_reviews:
                            print(f"✅ Request {REQUEST_ID} found in completed reviews (memory)")
                        else:
                            print(f"❌ Request {REQUEST_ID} NOT found in memory")
                            print("   This explains why the error occurred!")
                            print("   The application may have restarted and lost in-memory state.")
                else:
                    print("❌ HDL Agent not found in coordinator")
        else:
            print("❌ Agent Coordinator not initialized")
            
    except Exception as e:
        print(f"⚠️  Could not check Agent Coordinator: {e}")
    
    # Summary and recommendations
    print("\n" + "="*80)
    print("SUMMARY AND RECOMMENDATIONS")
    print("="*80)
    print("""
Based on the analysis, the error "Review request not found" occurs when:

1. **Application Restart**: The Cloud Run instance restarted, losing in-memory state
   - Solution: Ensure hdl_reviews table exists and is being used for persistence
   
2. **Request Expired**: The review request expired before the user responded
   - Solution: Check the expires_at timestamp in the database
   
3. **Database Persistence Failed**: The request was never saved to the database
   - Solution: Check logs for database errors during request creation
   
4. **Table Missing**: The hdl_reviews table doesn't exist
   - Solution: Run this script to create the table automatically

RECOMMENDED FIXES:
- ✅ Run this diagnostic script to identify the issue
- ✅ Ensure database connectivity is working
- ✅ Verify hdl_reviews table exists and has correct schema
- ✅ Check Cloud Run logs for any errors during request creation
- ✅ Consider increasing review expiration time if users need more time to respond
- ✅ Add better error messages to help users understand what went wrong
    """)
    
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
