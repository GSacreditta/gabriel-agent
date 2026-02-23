# HDL Request Error Fix - Summary

## Error: "Review request not found"
**Request ID:** `e604366c-6712-4d40-8eab-685d835dd1fe`

## Root Cause
When a user responds to an HDL (Human-in-the-Loop) review request in Slack, the system couldn't find the request because:

1. The Cloud Run application restarted, losing in-memory state
2. The database fallback didn't work properly due to:
   - Silent failures in database lookup
   - Missing initialization of the `hdl_reviews` table on startup
   - No recovery of pending reviews after restart

## Fixes Implemented

### 1. Enhanced Database Error Logging
**File:** `app/agents/hdl_agent.py` - `_load_review_from_db()`

**Changes:**
- Added explicit error logging for coordinator unavailability
- Improved error messages for database query failures
- Added logging of full DB result on error
- Distinguish between "not found" vs "query failed"

**Code:**
```python
if db_result.get('status') == 'success':
    rows = db_result.get('result', [])
    if rows:
        # Process result
        ...
    else:
        self.logger.warning(f"⚠️ Review {request_id} not found in database (query returned no rows)")
        return None
else:
    error_msg = db_result.get('message', 'Unknown database error')
    self.logger.error(f"❌ Database query failed for {request_id}: {error_msg}")
    self.logger.error(f"DB Result: {db_result}")
    return None
```

### 2. Better User Error Messages
**File:** `app/agents/hdl_agent.py` - `process_human_response()`

**Changes:**
- Replaced generic "Review request not found" with detailed error
- Include diagnostic information (checked memory, checked database, coordinator status)
- Provide actionable guidance to users

**Code:**
```python
if not review_data:
    error_details = {
        "request_id": request_id,
        "checked_memory": True,
        "found_in_memory": found_in_memory,
        "checked_database": True,
        "coordinator_available": self.coordinator is not None,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return {
        "status": "error", 
        "message": "Review request not found. This request may have expired, been already processed, or the application may have restarted. Please request a new review if needed.",
        "details": error_details,
        "request_id": request_id
    }
```

### 3. Restore Pending Reviews on Startup
**File:** `app/agents/hdl_agent.py` - New method `restore_pending_reviews()`

**Changes:**
- Added method to query database for pending, non-expired reviews
- Restores them to in-memory `pending_reviews` dict on startup
- Handles database errors gracefully

**Code:**
```python
async def restore_pending_reviews(self):
    """Restore pending reviews from database after restart"""
    db_result = await self.send_message("DB_AGENT", {
        "action": "execute_query",
        "data": {
            "query": """
                SELECT request_id, source_agent, request_type, data, 
                       message, status, created_at, expires_at
                FROM hdl_reviews 
                WHERE status = 'pending' AND expires_at > NOW()
                ORDER BY created_at DESC
            """,
            "params": []
        }
    })
    
    if db_result.get('status') == 'success':
        rows = db_result.get('result', [])
        for row in rows:
            review_data = {...}  # Parse row
            self.pending_reviews[review_data['request_id']] = review_data
        
        self.logger.info(f"✅ Restored {len(rows)} pending review(s) from database")
```

### 4. HDL Agent Initialization
**File:** `app/agents/hdl_agent.py` - New method `initialize_agent()`

**Changes:**
- Added initialization method called on startup
- Ensures `hdl_reviews` table exists
- Restores pending reviews from database
- Prevents duplicate initialization

**Code:**
```python
async def initialize_agent(self):
    """Initialize HDL Agent - ensure database tables and restore pending reviews"""
    if self._initialized:
        return
    
    # Ensure database table exists
    await self._ensure_hdl_reviews_table()
    
    # Restore any pending reviews from database
    await self.restore_pending_reviews()
    
    self._initialized = True
```

### 5. Call Initialization from Agent Coordinator
**File:** `app/agents/agent_coordinator.py` - `start_coordinator()`

**Changes:**
- Added call to `initialize_agent()` during coordinator startup
- Ensures HDL Agent is fully initialized before processing requests
- Graceful error handling if initialization fails

**Code:**
```python
# Initialize HDL Agent with database tables and restore pending reviews
logger.info("Initializing HDL Agent with database persistence...")
try:
    hdl_agent = self.agent_instances.get("HDL_AGENT")
    if hdl_agent and hasattr(hdl_agent, 'initialize_agent'):
        await hdl_agent.initialize_agent()
        logger.info("✅ HDL Agent initialization completed")
except Exception as e:
    logger.error(f"❌ Failed to initialize HDL Agent: {e}")
    logger.warning("HDL Agent will continue without full initialization")
```

### 6. Enhanced Slack Error Messages
**File:** `app/services/slack_service.py` - `_handle_message()`

**Changes:**
- Improved error messages shown to users in Slack
- Distinguish between "not found" and other errors
- Provide helpful context and next steps

**Code:**
```python
if "not found" in error_msg.lower():
    error_response += (
        "**What this means:**\n"
        "This review request may have:\n"
        "• Expired (requests are valid for a limited time)\n"
        "• Already been processed\n"
        "• Been lost due to an application restart\n\n"
        "**What to do:**\n"
        "Please request a new review if this action is still needed."
    )
```

## Impact

### Before Fix:
- ❌ Application restart → all pending reviews lost
- ❌ Users get generic "Review request not found" error
- ❌ No way to recover from restart
- ❌ Silent database failures
- ❌ Poor debugging visibility

### After Fix:
- ✅ Application restart → pending reviews restored from database
- ✅ Users get detailed error with next steps
- ✅ Automatic recovery from restart
- ✅ Explicit database error logging
- ✅ Full diagnostic information in logs

## Testing

### Test Scenarios:

1. **Normal Flow** (should work before and after fix):
   - Create review request
   - User responds immediately
   - ✅ Request processed successfully

2. **Application Restart** (FIXED):
   - Create review request
   - Restart Cloud Run application
   - User responds
   - ✅ Request found in database and processed

3. **Expired Request** (Better error message):
   - Create review request
   - Wait for expiration (> 12 hours)
   - User responds
   - ✅ Clear error message about expiration

4. **Database Error** (Better logging):
   - Create review request
   - Simulate database failure
   - User responds
   - ✅ Detailed error logs for debugging

### How to Test:

```bash
# 1. Deploy the fixes
gcloud builds submit --config cloudbuild.yaml

# 2. Create a test review request via Slack or API
# (This will create a request and persist it to database)

# 3. Restart the Cloud Run service to simulate restart
gcloud run services update gabriel-agent --region us-east1

# 4. Respond to the review request in Slack
# (Should now work - request restored from database)

# 5. Check logs for confirmation
gcloud logs read --service gabriel-agent --limit 100
```

## Monitoring

### Log Messages to Watch For:

**Success:**
```
✅ HDL Agent initialization completed
✅ Restored 3 pending review(s) from database
✅ Review loaded from DB: e604366c-6712-4d40-8eab-685d835dd1fe
```

**Warnings:**
```
⚠️ Review e604366c-6712-4d40-8eab-685d835dd1fe not found in database (query returned no rows)
```

**Errors:**
```
❌ Database query failed for e604366c-6712-4d40-8eab-685d835dd1fe: connection timeout
❌ Failed to initialize HDL Agent: ...
```

## Configuration

### Review Expiration
Default expiration is set in `HDLAgent.__init__()`:

```python
self.review_timeout_hours = 12  # Reviews expire after 12 hours
```

To change: Update this value in `app/agents/hdl_agent.py`

### Database Table Schema
The `hdl_reviews` table is automatically created with this schema:

```sql
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
```

## Deployment Checklist

- [x] Updated `app/agents/hdl_agent.py` with better error handling
- [x] Added `restore_pending_reviews()` method
- [x] Added `initialize_agent()` method
- [x] Updated `app/agents/agent_coordinator.py` to call initialization
- [x] Updated `app/services/slack_service.py` with better error messages
- [x] Created diagnostic script `debug_request.py`
- [x] Created analysis document `REQUEST_ERROR_ANALYSIS.md`
- [x] Created this summary document

## Next Steps

1. **Deploy the fixes:**
   ```bash
   git add .
   git commit -m "Fix HDL review request persistence and error handling"
   git push
   ```

2. **Monitor the deployment:**
   - Check Cloud Run logs for successful initialization
   - Verify pending reviews are restored on startup
   - Test with a real review request

3. **If the specific request is still needed:**
   - Ask the system to create a new review request
   - The old request ID `e604366c-6712-4d40-8eab-685d835dd1fe` cannot be recovered if it's not in the database

4. **Future Improvements:**
   - Add metrics/monitoring for review request lifecycle
   - Implement request expiration notifications
   - Add manual review request lookup API endpoint
   - Consider longer expiration times if users need more time to respond

## Questions?

If you encounter any issues with these fixes, check:

1. **Database connectivity**: Is the Cloud SQL connection working?
2. **Table creation**: Did the `hdl_reviews` table get created?
3. **Agent initialization**: Did the HDL Agent initialize successfully?
4. **Logs**: What do the Cloud Run logs show?

Run the diagnostic script to investigate:
```bash
python3 debug_request.py
```

(Note: This requires dependencies to be installed and database access configured)
