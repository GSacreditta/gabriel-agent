# Database Layer Error Handling Improvements

## Overview
This document details the comprehensive improvements made to the database layer in the Gabriel Agent system, specifically addressing error handling, connection management, and graceful degradation.

## Key Enhancements

### 1. **Strict Mode Implementation** ✅

All database operations now support an optional `strict` parameter that controls error handling behavior:

```python
# Graceful degradation (default)
result = await db_agent.match_entity("John Doe", strict=False)
# Returns None if database unavailable

# Strict mode - fails fast
result = await db_agent.match_entity("John Doe", strict=True)
# Raises DatabaseUnavailableError if database unavailable
```

**Benefits:**
- **Flexibility**: Caller decides whether to fail or degrade gracefully
- **Predictability**: Clear expectations for error handling
- **Developer Control**: Different operations can use different modes based on criticality

### 2. **Custom Exception Hierarchy** ✅

Created comprehensive exception classes in `app/core/exceptions.py`:

```python
GabrielAgentException (base)
├── DatabaseException
│   ├── DatabaseUnavailableError      # DB service unavailable
│   ├── DatabaseConnectionError       # Connection failed
│   ├── EntityNotFoundError           # Entity not found
│   ├── TaskNotFoundError             # Task not found
│   └── DuplicateEntityError          # Duplicate entity
├── InvalidOperationError
└── ServiceUnavailableError
```

**Benefits:**
- **Precise Error Handling**: Catch specific errors
- **Better Debugging**: Clear error types and messages
- **Error Context**: Errors carry relevant information (entity_id, operation, etc.)

### 3. **Connection Management Improvements** ✅

Enhanced `ensure_database_connection()` method:

```python
async def ensure_database_connection(self, strict: bool = None) -> bool:
    """
    Ensure database connection with retry logic
    
    Features:
    - Lazy loading (connects on first use)
    - Retry mechanism (3 attempts by default)
    - Connection verification
    - Strict mode support
    """
```

**Features:**
- **Lazy Loading**: Database connects only when needed
- **Retry Logic**: 3 attempts with exponential backoff
- **Connection Verification**: Tests connection before using
- **Error Tracking**: Logs retry attempts and failures

### 4. **Comprehensive Error Handling** ✅

Every database operation now:
1. Checks database connection before executing
2. Handles connection failures appropriately
3. Logs errors with context
4. Returns meaningful error responses

**Example: Enhanced `match_entity()`**

```python
async def match_entity(
    self, 
    entity_name: str, 
    strict: bool = None
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
        
    try:
        # Ensure database connection (lazy loading)
        if not await self.ensure_database_connection(strict=strict):
            if strict:
                raise DatabaseUnavailableError("match_entity")
            return None  # Graceful degradation
        
        # ... rest of implementation
    except DatabaseUnavailableError:
        raise  # Re-raise if strict mode
    except Exception as e:
        self.logger.error(f"Error matching entity: {e}")
        if strict:
            raise
        return None
```

### 5. **All Operations Enhanced** ✅

The following operations now support strict mode and comprehensive error handling:

**Entity Operations:**
- `match_entity()` - Match by name
- `create_entity()` - Create new entity
- `get_entity()` - Get by ID
- `list_entities()` - List all entities

**Task Operations:**
- `create_task()` - Create new task
- `update_task_status()` - Update task status
- `get_tasks()` - Get tasks with filtering

**Obligation Operations:**
- `create_obligation()` - Create new obligation

**Authorization Operations:**
- `create_authorization()` - Create new authorization

**Document Operations:**
- `store_document_metadata()` - Store document metadata

**Raw SQL Operations:**
- `execute_query()` - Execute SELECT queries
- `execute_command()` - Execute INSERT/UPDATE/DELETE

### 6. **Message Handler Enhancement** ✅

The `handle_message()` method now:
- Extracts `strict` parameter from messages
- Uses appropriate error handling
- Returns structured error responses with error types
- Categorizes errors: `database_unavailable`, `not_found`, `internal_error`

```python
async def handle_message(self, source_agent: str, message: Dict[str, Any]) -> Dict[str, Any]:
    """Handle messages from other agents with enhanced error handling"""
    action = message.get('action')
    data = message.get('data', {})
    strict = message.get('strict', self.default_strict_mode)  # ✅ Extract strict mode
    
    try:
        if action == "match_entity":
            result = await self.match_entity(data.get('name'), strict=strict)
            return {"status": "success", "result": result}
        # ... other actions
        
    except DatabaseUnavailableError as e:
        return {"status": "error", "message": str(e), "error_type": "database_unavailable"}
    except (EntityNotFoundError, TaskNotFoundError) as e:
        return {"status": "error", "message": str(e), "error_type": "not_found"}
    except Exception as e:
        return {"status": "error", "message": str(e), "error_type": "internal_error"}
```

### 7. **Default Strict Mode** ✅

The `DBAgent` class now accepts a `default_strict_mode` parameter:

```python
# Graceful degradation by default
db_agent = DBAgent(default_strict_mode=False)

# Strict mode by default
db_agent = DBAgent(default_strict_mode=True)
```

This allows configuring the default behavior at agent initialization while still allowing per-operation overrides.

## Architecture Improvements

### Database Service (`app/core/database/service.py`)

Enhanced database service with:
- **Connection Pooling**: Configured pool size and overflow
- **Connection Health Checks**: Pre-ping to verify connections
- **Connection Recycling**: Automatic recycling after 1 hour
- **Cloud SQL Support**: Unix socket connections for Google Cloud SQL
- **Async Context Managers**: Proper session lifecycle management

```python
class DatabaseService:
    """Async database service with connection pooling"""
    
    async def initialize(self) -> bool:
        """Initialize with retry and error handling"""
        
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get session with automatic cleanup"""
        
    async def execute_query(self, query: str, params: Optional[Tuple] = None):
        """Execute SELECT queries"""
        
    async def execute_command(self, query: str, params: Optional[Tuple] = None):
        """Execute INSERT/UPDATE/DELETE commands"""
```

### Database Models (`app/models/database_models.py`)

Complete SQLAlchemy models:
- `Entity` - Individuals, organizations
- `Task` - Actionable tasks
- `Obligation` - Recurring obligations
- `Authorization` - Permissions and authorizations
- `DocumentMetadata` - Document processing metadata

With enumerations:
- `TaskStatus` - PENDING, IN_PROGRESS, DONE, CANCELLED
- `Frequency` - ONCE, DAILY, WEEKLY, MONTHLY, etc.

## Usage Examples

### Example 1: Critical Operation (Strict Mode)

```python
# Creating an entity must succeed or fail clearly
try:
    entity = await db_agent.create_entity({
        "name": "John Doe",
        "category": "Individual"
    }, strict=True)
    print(f"Entity created: {entity['entity_id']}")
except DatabaseUnavailableError:
    # Handle database unavailability
    send_alert("Database unavailable - entity creation failed")
except DuplicateEntityError:
    # Handle duplicate
    print("Entity already exists")
```

### Example 2: Non-Critical Query (Graceful Degradation)

```python
# Matching an entity can fail gracefully
entity = await db_agent.match_entity("John Doe", strict=False)

if entity is None:
    # Could be: not found, or database unavailable
    # Application continues with default behavior
    print("Entity not found or database unavailable")
else:
    print(f"Found entity: {entity['name']}")
```

### Example 3: Using Default Strict Mode

```python
# Initialize with strict mode as default
db_agent = DBAgent(default_strict_mode=True)

# All operations will be strict by default
entity = await db_agent.match_entity("John Doe")  # Will raise if DB unavailable

# Can override per operation
entity = await db_agent.match_entity("Jane Doe", strict=False)  # Graceful degradation
```

### Example 4: Message-Based Invocation

```python
# Via agent coordinator
response = await agent_coordinator.route_message(
    source="API",
    target="DB_AGENT",
    message={
        "action": "create_entity",
        "data": {"name": "John Doe", "category": "Individual"},
        "strict": True  # Enable strict mode for this operation
    }
)

if response["status"] == "error":
    error_type = response.get("error_type")
    if error_type == "database_unavailable":
        # Handle database unavailability
        pass
    elif error_type == "not_found":
        # Handle not found
        pass
```

## Error Response Format

All operations return structured error responses:

```python
{
    "status": "error",
    "message": "Database service unavailable for operation: create_entity",
    "error_type": "database_unavailable"  # or "not_found", "internal_error"
}
```

Success responses:

```python
{
    "status": "success",
    "result": {
        # Operation-specific result data
    }
}
```

## Migration Guide

### Before (Original Implementation)

```python
# Silent failure - returns None without indication of why
entity = await db_agent.match_entity("John Doe")

if entity is None:
    # Was it not found? Or database unavailable? Unknown!
    pass
```

### After (Enhanced Implementation)

```python
# Option 1: Graceful degradation (default)
entity = await db_agent.match_entity("John Doe", strict=False)
if entity is None:
    # Entity not found or database unavailable - handle gracefully
    pass

# Option 2: Fail fast (strict mode)
try:
    entity = await db_agent.match_entity("John Doe", strict=True)
    # Entity found and returned
except DatabaseUnavailableError:
    # Database unavailable - handle specifically
    pass
except Exception as e:
    # Other errors
    pass
```

## Testing Recommendations

### Unit Tests

```python
import pytest
from app.agents.db_agent import DBAgent
from app.core.exceptions import DatabaseUnavailableError

@pytest.mark.asyncio
async def test_match_entity_strict_mode_db_unavailable():
    """Test strict mode raises error when DB unavailable"""
    agent = DBAgent()
    agent.db_service = None  # Simulate unavailable DB
    
    with pytest.raises(DatabaseUnavailableError):
        await agent.match_entity("John Doe", strict=True)

@pytest.mark.asyncio
async def test_match_entity_graceful_mode_db_unavailable():
    """Test graceful mode returns None when DB unavailable"""
    agent = DBAgent()
    agent.db_service = None  # Simulate unavailable DB
    
    result = await agent.match_entity("John Doe", strict=False)
    assert result is None
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_create_entity_with_retry():
    """Test entity creation with connection retry"""
    agent = DBAgent()
    
    entity = await agent.create_entity({
        "name": "Test Entity",
        "category": "Test"
    }, strict=True)
    
    assert entity["entity_id"].startswith("E")
    assert entity["name"] == "Test Entity"
```

## Configuration

### Environment Variables

```bash
# Database connection
DB_HOST=localhost
DB_PORT=5432
DB_NAME=gabriel_agent
DB_USER=postgres
DB_PASSWORD=your_password

# For Google Cloud SQL
DB_CONNECTION_NAME=project:region:instance

# Agent configuration (optional)
DB_AGENT_DEFAULT_STRICT_MODE=false
DB_AGENT_MAX_RETRIES=3
DB_AGENT_CACHE_TTL=3600
```

## Performance Considerations

1. **Connection Pooling**: Configured with `pool_size=5` and `max_overflow=10`
2. **Entity Caching**: 1-hour TTL cache for entity matching
3. **Lazy Loading**: Database connects only when needed
4. **Connection Recycling**: Connections recycled after 1 hour

## Monitoring and Logging

All operations log:
- Connection attempts and failures
- Retry attempts
- Operation successes and failures
- Error details with context

Example logs:

```
INFO - [DB_AGENT] Entity matching: {'entity_name': 'John Doe', 'strict': True}
ERROR - Failed to establish database connection (attempt 1): Connection refused
INFO - ✅ Database connection established successfully
INFO - [DB_AGENT] Entity created: {'entity_id': 'E001', 'name': 'John Doe'}
```

## Summary

The enhanced database layer provides:

✅ **Flexible Error Handling** - Strict mode vs. graceful degradation  
✅ **Comprehensive Exceptions** - Clear, specific error types  
✅ **Connection Management** - Lazy loading, retry logic, pooling  
✅ **Consistent API** - All operations support strict mode  
✅ **Better Logging** - Detailed context for debugging  
✅ **Production Ready** - Cloud SQL support, connection pooling  
✅ **Developer Friendly** - Clear documentation and examples  
✅ **Testable** - Well-defined error cases and behaviors  

## Files Created/Modified

1. ✅ `app/core/exceptions.py` - Custom exception hierarchy
2. ✅ `app/agents/base_agent.py` - Base agent class
3. ✅ `app/agents/db_agent.py` - Enhanced DB agent with strict mode
4. ✅ `app/models/database_models.py` - SQLAlchemy models
5. ✅ `app/core/database/service.py` - Database service with pooling
6. ✅ `DATABASE_LAYER_IMPROVEMENTS.md` - This documentation

## Next Steps

1. **Integration**: Connect the DB agent to the agent coordinator in `main.py`
2. **Testing**: Write comprehensive unit and integration tests
3. **Monitoring**: Add metrics for database operations
4. **Documentation**: Add API documentation for all endpoints
5. **Migration**: Update existing code to use the enhanced DB agent

---

**Version**: 1.0  
**Date**: 2025-10-19  
**Author**: Gabriel Agent Team
