# Before & After: Database Layer Error Handling

## The Problem

### ❌ Before: Silent Failures

```python
async def match_entity(self, entity_name: str) -> Optional[Dict[str, Any]]:
    """Match entity by exact name"""
    
    # Ensure database connection (lazy loading)
    await self.ensure_database_connection()
    
    # Handle case where database connection failed
    if self.db_service is None:
        self.log_activity("Entity matching failed - no database connection")
        return None  # ⚠️ PROBLEM: Silent failure!
    
    # ... rest of implementation
```

**Issues:**
1. ❌ Returns `None` - could mean "not found" OR "database unavailable"
2. ❌ Caller cannot distinguish between different failure modes
3. ❌ No way to fail fast for critical operations
4. ❌ Difficult to debug production issues
5. ❌ Logs warning but doesn't propagate error

### Example of the Problem

```python
# Trying to create an entity - this is a CRITICAL operation
entity = await db_agent.match_entity("John Doe")

if entity is None:
    # Is it not found? Or is the database down? 
    # We don't know! ⚠️
    entity = await db_agent.create_entity({
        "name": "John Doe",
        "category": "Individual"
    })
    # This might also fail silently! ⚠️
```

## The Solution

### ✅ After: Configurable Error Handling with Strict Mode

```python
async def match_entity(
    self, 
    entity_name: str,
    strict: bool = None  # ✅ NEW: Configurable behavior
) -> Optional[Dict[str, Any]]:
    """
    Match entity by exact name
    
    Args:
        entity_name: Name of entity to match
        strict: If True, raise DatabaseUnavailableError when DB unavailable.
               If False/None, return None gracefully.
    
    Returns:
        Entity data if found, None if not found or DB unavailable (when strict=False)
        
    Raises:
        DatabaseUnavailableError: If strict=True and database unavailable
    """
    if strict is None:
        strict = self.default_strict_mode
        
    # Ensure database connection (lazy loading)
    if not await self.ensure_database_connection(strict=strict):
        # Database unavailable
        if strict:
            raise DatabaseUnavailableError("match_entity")  # ✅ Explicit error
        self.log_activity("Entity matching failed - no database connection")
        return None  # ✅ Graceful degradation (when strict=False)
    
    # ... rest of implementation
```

**Benefits:**
1. ✅ **Fail Fast**: Critical operations can raise explicit errors
2. ✅ **Graceful Degradation**: Non-critical operations can continue
3. ✅ **Clear Intent**: Caller explicitly chooses behavior
4. ✅ **Better Debugging**: Detailed error messages with context
5. ✅ **Flexible**: Per-operation or per-agent default

## Usage Patterns

### Pattern 1: Critical Operations (Strict Mode)

```python
# ✅ AFTER: Critical operation - must succeed or fail clearly
try:
    entity = await db_agent.match_entity("John Doe", strict=True)
    if entity is None:
        # Definitely not found - create it
        entity = await db_agent.create_entity({
            "name": "John Doe",
            "category": "Individual"
        }, strict=True)
    else:
        # Found it - use it
        process_entity(entity)
        
except DatabaseUnavailableError as e:
    # Database is down - alert operations team
    logger.error(f"Critical: Database unavailable - {e}")
    send_alert("Database unavailable for entity creation")
    raise  # Stop execution
```

### Pattern 2: Non-Critical Operations (Graceful Mode)

```python
# ✅ AFTER: Non-critical operation - can continue without DB
entity = await db_agent.match_entity("John Doe", strict=False)

if entity is None:
    # Either not found OR database unavailable
    # Use defaults and continue
    logger.warning("Entity not available - using defaults")
    entity = get_default_entity()
else:
    # Found it
    process_entity(entity)

# Application continues regardless of DB status
continue_processing()
```

### Pattern 3: Default Strict Mode

```python
# ✅ Configure at initialization
db_agent = DBAgent(default_strict_mode=True)

# All operations are strict by default
entity = await db_agent.match_entity("John Doe")  # Raises if DB down

# Can override per operation
entity = await db_agent.match_entity("Jane Doe", strict=False)  # Graceful
```

## Error Handling Comparison

### ❌ Before: Ambiguous Errors

```python
entity = await db_agent.match_entity("John Doe")

if entity is None:
    # What does None mean?
    # - Entity not found in database?
    # - Database connection failed?
    # - Query execution error?
    # - Network timeout?
    # We don't know! ⚠️
    pass
```

### ✅ After: Clear Error Types

```python
try:
    entity = await db_agent.match_entity("John Doe", strict=True)
    
    if entity is None:
        # Definitely not found - database is working
        logger.info("Entity not found: John Doe")
    else:
        # Found it
        logger.info(f"Entity found: {entity['entity_id']}")
        
except DatabaseUnavailableError as e:
    # Database is unavailable - specific error
    logger.error(f"Database unavailable: {e}")
    alert_ops("Database down")
    
except DatabaseConnectionError as e:
    # Connection failed - network/config issue
    logger.error(f"Connection failed: {e}")
    alert_ops("Database connection failed")
    
except Exception as e:
    # Other unexpected errors
    logger.error(f"Unexpected error: {e}")
    raise
```

## Message-Based Invocation

### ❌ Before: No Error Control

```python
response = await coordinator.route_message(
    source="API",
    target="DB_AGENT",
    message={
        "action": "create_entity",
        "data": {"name": "John Doe"}
    }
)

# Response: {"status": "success"} or {"status": "error", "message": "..."}
# But we can't control error behavior!
```

### ✅ After: Strict Mode in Messages

```python
response = await coordinator.route_message(
    source="API",
    target="DB_AGENT",
    message={
        "action": "create_entity",
        "data": {"name": "John Doe"},
        "strict": True  # ✅ Control error behavior per message
    }
)

# Enhanced error responses
if response["status"] == "error":
    error_type = response.get("error_type")
    
    if error_type == "database_unavailable":
        # Database is down
        alert_ops("Database unavailable")
        
    elif error_type == "not_found":
        # Resource not found
        logger.warning("Entity not found")
        
    elif error_type == "internal_error":
        # Other errors
        logger.error(f"Internal error: {response['message']}")
```

## Connection Management

### ❌ Before: Basic Connection Check

```python
async def ensure_database_connection(self):
    """Ensure database connection is established (lazy loading with retry logic)"""
    if self.db_service is not None:
        return  # Already connected
    
    try:
        self.logger.info("Establishing database connection...")
        self.db_service = await get_database_service()
        await self.db_service.create_tables()
        self.log_activity("Database connection established successfully")
    except Exception as e:
        self.logger.error(f"Failed to establish database connection: {e}")
        self.db_service = None
        # Don't raise - let calling methods handle gracefully with None db_service
```

**Issues:**
1. ❌ Single connection attempt (no retry)
2. ❌ No way to propagate errors
3. ❌ Returns void (caller must check `db_service`)

### ✅ After: Robust Connection Management

```python
async def ensure_database_connection(self, strict: bool = None) -> bool:
    """
    Ensure database connection is established
    
    Features:
    - Retry logic (3 attempts)
    - Connection verification
    - Strict mode support
    - Returns success status
    """
    if strict is None:
        strict = self.default_strict_mode
        
    if self.db_service is not None:
        return True  # Already connected
    
    # Try to establish connection with retry logic
    last_error = None
    for attempt in range(self.max_connection_retries):
        try:
            self.logger.info(f"Establishing database connection (attempt {attempt + 1}/{self.max_connection_retries})...")
            self.db_service = await get_database_service()
            
            # Verify connection is working
            if self.db_service.is_initialized:
                await self.db_service.create_tables()
                self.log_activity("Database connection established successfully")
                self.connection_retry_count = 0
                return True  # ✅ Success
            else:
                last_error = Exception("Database service not properly initialized")
                
        except Exception as e:
            last_error = e
            self.logger.error(f"Failed to establish database connection (attempt {attempt + 1}): {e}")
            self.db_service = None
    
    # All retry attempts failed
    self.connection_retry_count += 1
    error_msg = f"Failed to establish database connection after {self.max_connection_retries} attempts"
    self.logger.error(error_msg)
    
    if strict:
        raise DatabaseConnectionError(error_msg, last_error)  # ✅ Explicit error
    
    return False  # ✅ Clear failure indication
```

**Benefits:**
1. ✅ Retry logic (3 attempts by default)
2. ✅ Connection verification
3. ✅ Returns success status
4. ✅ Raises error in strict mode
5. ✅ Tracks retry count for monitoring

## Exception Hierarchy

### ❌ Before: Generic Exceptions

```python
try:
    entity = await db_agent.create_entity(data)
except Exception as e:
    # What kind of error is it?
    # - Database unavailable?
    # - Duplicate entity?
    # - Invalid data?
    # - Network timeout?
    # We have to parse the error message! ⚠️
    logger.error(f"Error: {e}")
```

### ✅ After: Specific Exception Types

```python
try:
    entity = await db_agent.create_entity(data, strict=True)
    
except DatabaseUnavailableError as e:
    # Database service unavailable
    logger.error(f"Database unavailable: {e}")
    alert_ops("Database down")
    
except DatabaseConnectionError as e:
    # Connection failed
    logger.error(f"Connection failed: {e.original_error}")
    retry_later()
    
except DuplicateEntityError as e:
    # Entity already exists
    logger.warning(f"Duplicate entity: {e.entity_name}")
    existing = await db_agent.match_entity(e.entity_name)
    use_existing(existing)
    
except EntityNotFoundError as e:
    # Entity not found
    logger.warning(f"Entity not found: {e.entity_id}")
    create_new()
    
except Exception as e:
    # Other unexpected errors
    logger.error(f"Unexpected error: {e}")
    raise
```

## Logging Improvements

### ❌ Before: Basic Logging

```
INFO - DB Agent initialized - using lazy loading
INFO - Database connection established successfully
INFO - Entity matching failed - no database connection
```

### ✅ After: Detailed Context Logging

```
INFO - [DB_AGENT] DB Agent initialized - using lazy loading for database connection
INFO - Establishing database connection (attempt 1/3)...
INFO - Using PostgreSQL connection: localhost:5432/gabriel_agent
INFO - ✅ Database service initialized successfully
INFO - ✅ Database tables created successfully
INFO - [DB_AGENT] Entity matching: {'entity_name': 'John Doe', 'strict': True}
INFO - [DB_AGENT] Entity created: {'entity_id': 'E001', 'name': 'John Doe'}
ERROR - Failed to establish database connection (attempt 1): Connection refused
ERROR - Failed to establish database connection (attempt 2): Connection refused
ERROR - Failed to establish database connection (attempt 3): Connection refused
ERROR - ❌ Failed to establish database connection after 3 attempts
ERROR - Database unavailable for create_entity: Database service unavailable
```

## Summary: Key Improvements

| Aspect | Before | After |
|--------|--------|-------|
| **Error Handling** | Silent failures (returns None) | Configurable (strict vs. graceful) |
| **Error Types** | Generic exceptions | Specific exception hierarchy |
| **Connection Management** | Single attempt, no retry | Retry logic (3 attempts) |
| **Error Propagation** | Always swallowed | Raised in strict mode |
| **Caller Control** | None | Per-operation strict mode |
| **Debugging** | Ambiguous (None = ?) | Clear error types and messages |
| **Production Ready** | Basic | Retry, pooling, Cloud SQL |
| **Logging** | Minimal | Detailed with context |
| **Testability** | Difficult | Well-defined error cases |
| **Documentation** | Minimal | Comprehensive |

## Migration Example

### ❌ Before: Existing Code

```python
# Existing code that needs migration
async def process_document(doc_data):
    # Match entity (silent failure)
    entity = await db_agent.match_entity(doc_data['entity_name'])
    
    if entity is None:
        # Create entity (silent failure)
        entity = await db_agent.create_entity({
            "name": doc_data['entity_name'],
            "category": "Unknown"
        })
    
    # Store document (silent failure)
    result = await db_agent.store_document_metadata({
        "file_name": doc_data['file_name'],
        "entity_id": entity['entity_id']
    })
    
    return result
```

### ✅ After: Migrated Code

```python
# Migrated code with proper error handling
async def process_document(doc_data):
    try:
        # Match entity (strict - must work or fail)
        entity = await db_agent.match_entity(
            doc_data['entity_name'], 
            strict=True
        )
        
        if entity is None:
            # Not found - create it (strict)
            entity = await db_agent.create_entity({
                "name": doc_data['entity_name'],
                "category": "Unknown"
            }, strict=True)
        
        # Store document (strict - critical operation)
        result = await db_agent.store_document_metadata({
            "file_name": doc_data['file_name'],
            "entity_id": entity['entity_id']
        }, strict=True)
        
        return result
        
    except DatabaseUnavailableError:
        # Database down - alert and fail
        logger.error("Database unavailable - cannot process document")
        alert_ops("Database unavailable")
        raise
        
    except DuplicateEntityError as e:
        # Entity exists - fetch and use it
        logger.warning(f"Entity exists: {e.entity_name}")
        entity = await db_agent.match_entity(e.entity_name, strict=True)
        # Continue with existing entity...
```

---

**Result**: Clear, predictable error handling with flexibility to choose between fail-fast and graceful degradation based on operation criticality.
