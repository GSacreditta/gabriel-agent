# HDL Request Error Analysis

## Request ID: `e604366c-6712-4d40-8eab-685d835dd1fe`

## Error Description
The error "Review request not found" occurs when a user responds to an HDL (Human-in-the-Loop) review request in Slack, but the system cannot find the request.

## Root Cause Analysis

### How HDL Reviews Work

1. **Request Creation** (`app/agents/hdl_agent.py:209-240`):
   - HDL Agent creates a review request with a unique UUID
   - Stores it in **memory** (`self.pending_reviews`)
   - Persists it to **database** (`hdl_reviews` table)
   - Sends message to Slack with the Request ID

2. **User Response** (`app/services/slack_service.py:440-550`):
   - User responds to the Slack message in a thread
   - Slack service extracts the Request ID from the parent message
   - Routes to HDL Agent's `process_human_response` action

3. **Request Lookup** (`app/agents/hdl_agent.py:296-316`):
   - First checks **in-memory** (`pending_reviews` dict)
   - If not found, queries **database** (`hdl_reviews` table)
   - If still not found, returns "Review request not found" error

### Why This Error Occurs

#### ✅ Most Likely Cause: **Application Restart**
- Cloud Run instances restart periodically or on deployments
- In-memory state (`pending_reviews`) is lost on restart
- The database fallback should work, but something is preventing it

#### Possible Issues:

1. **`hdl_reviews` Table Missing** (HIGH PROBABILITY)
   ```sql
   -- Table may not exist yet
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
   - Table creation is called in `_ensure_hdl_reviews_table()` 
   - But this is only called during `request_human_review()`
   - If the app restarts AFTER creating a request, the table might exist but the in-memory state is gone

2. **Database Query Failing Silently**
   ```python
   # In _load_review_from_db (line 131-170)
   if not self.coordinator:
       self.logger.warning("No coordinator available for database access")
       return None  # Fails silently!
   ```
   - If the coordinator is not properly initialized, database lookups fail
   - No error is raised, just returns None

3. **DB_AGENT Not Handling Queries Properly**
   - The `execute_query` action requires DB service to be initialized
   - If database connection fails, it returns `{"status": "error"}`
   - HDL Agent doesn't check the error status properly

4. **Request Expired**
   - Reviews have an expiration time (default: 1 hour?)
   - Expired requests might be cleaned up from the database

## Code Issues Found

### Issue 1: Silent Failure in Database Lookup
**Location**: `app/agents/hdl_agent.py:131-170`

```python
async def _load_review_from_db(self, request_id: str) -> Optional[Dict[str, Any]]:
    if not self.coordinator:
        self.logger.warning("No coordinator available for database access")
        return None  # ❌ Silent failure
    
    db_result = await self.send_message("DB_AGENT", { ... })
    
    if db_result.get('status') == 'success' and db_result.get('result'):
        # Process result
        ...
    else:
        self.logger.error(f"Failed to load review from DB: {db_result.get('message')}")
        return None  # ❌ No indication of why it failed
```

**Problem**: If the database query fails, it just logs an error and returns None. The calling code can't distinguish between "not found" and "database error".

### Issue 2: No Error Message to User
**Location**: `app/agents/hdl_agent.py:315-316`

```python
if not review_data:
    return {"status": "error", "message": "Review request not found"}
```

**Problem**: Generic error message doesn't help the user understand what happened.

### Issue 3: Coordinator Dependency
**Location**: `app/agents/hdl_agent.py:133-136`

```python
if not self.coordinator:
    self.logger.warning("No coordinator available for database access")
    return None
```

**Problem**: The HDL Agent can't access the database without the coordinator. If there's any initialization issue with the coordinator, all database operations fail.

## Immediate Fixes Needed

### Fix 1: Better Error Messages
```python
if not review_data:
    # Provide more context in the error message
    return {
        "status": "error", 
        "message": "Review request not found. This may have expired or the application restarted. Please request a new review.",
        "request_id": request_id,
        "details": {
            "checked_memory": True,
            "checked_database": True,
            "coordinator_available": self.coordinator is not None
        }
    }
```

### Fix 2: Explicit Database Error Handling
```python
async def _load_review_from_db(self, request_id: str) -> Optional[Dict[str, Any]]:
    if not self.coordinator:
        self.logger.error("Cannot load review: No coordinator available")
        raise RuntimeError("HDL Agent not properly initialized - coordinator missing")
    
    db_result = await self.send_message("DB_AGENT", { ... })
    
    if db_result.get('status') != 'success':
        error_msg = db_result.get('message', 'Unknown error')
        self.logger.error(f"Database query failed: {error_msg}")
        raise RuntimeError(f"Database error: {error_msg}")
    
    # ... rest of the code
```

### Fix 3: Table Initialization on Startup
Ensure the `hdl_reviews` table is created when the HDL Agent starts, not just when the first review is created.

```python
# In HDL Agent __init__ or startup
async def initialize(self):
    """Initialize HDL Agent and ensure database tables exist"""
    await self._ensure_hdl_reviews_table()
    self.logger.info("HDL Agent initialized with database persistence")
```

### Fix 4: Restore Active Reviews on Startup
When the agent starts, load any pending reviews from the database:

```python
async def restore_pending_reviews(self):
    """Restore pending reviews from database after restart"""
    try:
        db_result = await self.send_message("DB_AGENT", {
            "action": "execute_query",
            "data": {
                "query": """
                    SELECT request_id, source_agent, request_type, data, 
                           message, status, created_at, expires_at
                    FROM hdl_reviews 
                    WHERE status = 'pending' AND expires_at > NOW()
                """,
                "params": []
            }
        })
        
        if db_result.get('status') == 'success':
            for row in db_result.get('result', []):
                review_data = self._row_to_review_data(row)
                self.pending_reviews[review_data['request_id']] = review_data
            
            self.logger.info(f"Restored {len(self.pending_reviews)} pending reviews from database")
    except Exception as e:
        self.logger.error(f"Failed to restore pending reviews: {e}")
```

## Recommended Actions

### For You (Developer):

1. **Add Better Logging**
   - Add request ID to all log messages
   - Log when requests are created, persisted, loaded from DB
   - Log database operation results

2. **Improve Error Handling**
   - Don't fail silently - raise exceptions or return detailed error info
   - Provide helpful error messages to users
   - Distinguish between "not found", "expired", and "database error"

3. **Add Startup Recovery**
   - Restore pending reviews from database on startup
   - Ensure tables are created before any operations

4. **Add Monitoring**
   - Track how many reviews are created vs completed
   - Alert on database failures
   - Monitor review expiration rates

### For Your Users:

1. **Immediate Workaround**:
   - If you get "Review request not found", ask the system to create a new review request
   - Don't wait too long to respond (requests may expire)

2. **Check Expiration**:
   - How long ago was the request created?
   - Default expiration is typically 1-24 hours

## Testing the Fix

After implementing fixes, test:

1. **Normal Flow**: Create request, respond immediately - should work
2. **After Restart**: Create request, restart app, respond - should work with DB fallback
3. **Expired Request**: Create request, wait for expiration, respond - should give clear error
4. **Database Down**: Create request, disconnect database, respond - should give clear error

## Next Steps

1. Check Cloud Run logs for the specific request ID to see:
   - Was it created successfully?
   - Was it persisted to database?
   - What error occurred during lookup?

2. Check database directly:
   ```sql
   SELECT * FROM hdl_reviews 
   WHERE request_id = 'e604366c-6712-4d40-8eab-685d835dd1fe';
   ```

3. Implement the fixes above

4. Deploy and test

Would you like me to implement these fixes in the code?
