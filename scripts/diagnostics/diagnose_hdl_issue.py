"""
Diagnostic Script for HDL Review Request Issue
Request ID: 64068f63-3789-41e0-82f3-8809a0a8be86

This will check:
1. Database connectivity
2. hdl_reviews table existence
3. Whether the request exists in database
4. Whether DB_AGENT execute_command is working
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def diagnose():
    """Run diagnostics"""
    
    REQUEST_ID = "64068f63-3789-41e0-82f3-8809a0a8be86"
    
    print("\n" + "="*80)
    print("HDL REVIEW REQUEST DIAGNOSTIC")
    print(f"Request ID: {REQUEST_ID}")
    print("="*80 + "\n")
    
    # Step 1: Check Database Service
    print("Step 1: Checking Database Service...")
    try:
        from app.core.database.service import get_database_service
        db_service = await get_database_service()
        
        if not db_service.is_initialized:
            print("❌ CRITICAL: Database service is NOT initialized!")
            print("   This is likely why review requests are failing.")
            print("   The database connection is not working.")
            return
        
        print("✅ Database service is initialized")
        
        # Test basic query
        test_result = await db_service.execute_query("SELECT 1 as test", ())
        if test_result and test_result[0][0] == 1:
            print("✅ Database queries are working")
        else:
            print("❌ Database queries are NOT working properly")
            return
            
    except Exception as e:
        print(f"❌ CRITICAL ERROR: Cannot access database: {e}")
        import traceback
        print(traceback.format_exc())
        return
    
    # Step 2: Check if hdl_reviews table exists
    print("\nStep 2: Checking hdl_reviews table...")
    try:
        table_check = await db_service.execute_query(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'hdl_reviews'
            )
            """,
            ()
        )
        
        table_exists = table_check[0][0] if table_check else False
        
        if table_exists:
            print("✅ hdl_reviews table exists")
            
            # Check table structure
            columns = await db_service.execute_query(
                """
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'hdl_reviews'
                ORDER BY ordinal_position
                """,
                ()
            )
            
            print(f"   Table has {len(columns)} columns:")
            for col in columns:
                print(f"   - {col[0]}: {col[1]}")
                
        else:
            print("❌ hdl_reviews table does NOT exist!")
            print("   This is why reviews aren't being persisted.")
            print("\n   Creating table now...")
            
            await db_service.execute_command(
                """
                CREATE TABLE hdl_reviews (
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
        print(f"❌ Error checking table: {e}")
        import traceback
        print(traceback.format_exc())
        return
    
    # Step 3: Search for the specific request
    print(f"\nStep 3: Searching for request {REQUEST_ID}...")
    try:
        result = await db_service.execute_query(
            """
            SELECT request_id, source_agent, request_type, status, 
                   created_at, expires_at, message
            FROM hdl_reviews 
            WHERE request_id = %s
            """,
            (REQUEST_ID,)
        )
        
        if result:
            print("✅ Request FOUND in database!")
            row = result[0]
            print(f"   Request ID: {row[0]}")
            print(f"   Source Agent: {row[1]}")
            print(f"   Type: {row[2]}")
            print(f"   Status: {row[3]}")
            print(f"   Created: {row[4]}")
            print(f"   Expires: {row[5]}")
            print(f"   Message: {row[6][:100] if row[6] else 'None'}...")
        else:
            print("❌ Request NOT FOUND in database!")
            print("   This means the request was never persisted to the database.")
            print("   The database write is FAILING SILENTLY.")
            
    except Exception as e:
        print(f"❌ Error searching for request: {e}")
        import traceback
        print(traceback.format_exc())
    
    # Step 4: Check recent requests
    print("\nStep 4: Checking recent HDL requests in database...")
    try:
        recent = await db_service.execute_query(
            """
            SELECT request_id, source_agent, status, created_at
            FROM hdl_reviews 
            ORDER BY created_at DESC
            LIMIT 5
            """,
            ()
        )
        
        if recent:
            print(f"✅ Found {len(recent)} recent request(s):")
            for i, row in enumerate(recent, 1):
                print(f"   {i}. {row[0][:20]}... | {row[1]} | {row[2]} | {row[3]}")
        else:
            print("⚠️  NO requests found in database at all!")
            print("   This confirms that database persistence is NOT working.")
            
    except Exception as e:
        print(f"❌ Error fetching recent requests: {e}")
        import traceback
        print(traceback.format_exc())
    
    # Step 5: Check Agent Coordinator
    print("\nStep 5: Checking Agent Coordinator and HDL Agent...")
    try:
        # Try to import and check agent coordinator
        from app.main import services
        
        if services.get("agent_coordinator"):
            print("✅ Agent Coordinator is initialized")
            
            coordinator = services["agent_coordinator"]
            hdl_agent = coordinator.agent_instances.get("HDL_AGENT")
            
            if hdl_agent:
                print("✅ HDL Agent is available")
                
                # Check if coordinator is set
                if hasattr(hdl_agent, 'coordinator') and hdl_agent.coordinator:
                    print("✅ HDL Agent has coordinator reference")
                else:
                    print("❌ HDL Agent does NOT have coordinator reference!")
                    print("   This is why database operations are failing!")
                
                # Check in-memory reviews
                if hasattr(hdl_agent, 'pending_reviews'):
                    pending_count = len(hdl_agent.pending_reviews)
                    print(f"   In-memory pending reviews: {pending_count}")
                    
                    if REQUEST_ID in hdl_agent.pending_reviews:
                        print(f"✅ Request {REQUEST_ID} found in memory!")
                    else:
                        print(f"❌ Request {REQUEST_ID} NOT in memory")
                        
                        # Check if it's in completed
                        if hasattr(hdl_agent, 'completed_reviews') and REQUEST_ID in hdl_agent.completed_reviews:
                            print(f"   Request is in COMPLETED reviews")
                        
            else:
                print("❌ HDL Agent not found in coordinator")
        else:
            print("❌ Agent Coordinator not initialized")
            print("   The application may not have started properly.")
            
    except Exception as e:
        print(f"⚠️  Could not check agents (may not be running): {e}")
    
    # Summary
    print("\n" + "="*80)
    print("DIAGNOSIS SUMMARY")
    print("="*80)
    print("""
Based on the analysis, the most likely issues are:

1. **Database writes are failing silently**
   - Review requests are created in memory
   - They're sent to Slack successfully
   - But _persist_review_to_db() is failing without raising errors
   
2. **Possible causes:**
   - HDL Agent doesn't have coordinator reference (can't call DB_AGENT)
   - hdl_reviews table doesn't exist
   - Database connection issues
   - execute_command action in DB_AGENT is failing

3. **Why you see "Review request not found":**
   - Request is created in memory
   - Sent to Slack (you receive it)
   - But when app restarts or request is processed, it's not in database
   - Not in memory either (cleared on restart or after processing)

NEXT STEPS:
1. Check Cloud Run logs for database errors during review creation
2. Ensure hdl_reviews table exists (script will create it)
3. Verify HDL Agent coordinator reference is set properly
4. Add error handling so database failures don't fail silently
    """)
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(diagnose())
