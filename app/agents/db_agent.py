"""
DB Agent - Database Operations Agent (Enhanced with Strict Mode)

Handles all structured data operations: entities, tasks, obligations, authorizations
Provides entity matching services to other agents

ENHANCEMENTS:
- Strict mode for operations (fail vs. graceful degradation)
- Comprehensive error handling with custom exceptions
- Database connection checks before every operation
- Retry logic for transient failures
- Better logging and error messages
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, date
import uuid
import json
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from .base_agent import BaseAgent
from ..models.database_models import Entity, Task, Obligation, Authorization, DocumentMetadata, TaskStatus, Frequency
from ..core.database.service import get_database_service
from ..core.exceptions import (
    DatabaseUnavailableError,
    DatabaseConnectionError,
    EntityNotFoundError,
    TaskNotFoundError,
    DuplicateEntityError
)


class DBAgent(BaseAgent):
    """Database Agent for structured data operations with enhanced error handling"""
    
    def __init__(self, default_strict_mode: bool = False):
        """
        Initialize DB Agent
        
        Args:
            default_strict_mode: If True, all operations will fail when DB unavailable by default.
                               Can be overridden per-operation.
        """
        super().__init__("DB_AGENT")
        
        # Database service
        self.db_service = None
        self.default_strict_mode = default_strict_mode
        
        # Entity matching cache for performance
        self.entity_cache = {}
        self.cache_ttl = 3600  # 1 hour cache
        
        # Connection retry settings
        self.max_connection_retries = 3
        self.connection_retry_count = 0
        
    async def initialize(self):
        """Initialize the DB Agent (legacy method - now uses lazy loading)"""
        self.log_activity("DB Agent initialized - using lazy loading for database connection")
        # Database connection now happens on first use via ensure_database_connection()
    
    async def ensure_database_connection(self, strict: bool = None) -> bool:
        """
        Ensure database connection is established (lazy loading with retry logic)
        
        Args:
            strict: If True, raise error on connection failure. If None, use default_strict_mode.
        
        Returns:
            bool: True if connection successful, False otherwise
            
        Raises:
            DatabaseConnectionError: If strict=True and connection fails
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
                    # Create tables if they don't exist
                    await self.db_service.create_tables()
                    self.log_activity("Database connection established successfully")
                    self.connection_retry_count = 0
                    return True
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
            raise DatabaseConnectionError(error_msg, last_error)
        
        return False
        
    async def get_capabilities(self) -> List[str]:
        """Return DB Agent capabilities"""
        return [
            "entity_operations",
            "entity_matching", 
            "task_management",
            "obligation_tracking",
            "authorization_management",
            "document_metadata_storage"
        ]
    
    async def handle_message(self, source_agent: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle messages from other agents with enhanced error handling"""
        action = message.get('action')
        data = message.get('data', {})
        # Extract strict mode from message or use default
        strict = message.get('strict', self.default_strict_mode)
        
        try:
            if action == "match_entity":
                result = await self.match_entity(data.get('name'), strict=strict)
                return {"status": "success", "result": result}
                
            elif action == "create_entity":
                result = await self.create_entity(data, strict=strict)
                return {"status": "success", "result": result}
                
            elif action == "get_entity":
                result = await self.get_entity(data.get('entity_id'), strict=strict)
                return {"status": "success", "result": result}
                
            elif action == "list_entities":
                result = await self.list_entities(strict=strict)
                return {"status": "success", "result": result}
                
            elif action == "create_task":
                result = await self.create_task(data, strict=strict)
                return {"status": "success", "result": result}
                
            elif action == "update_task_status":
                result = await self.update_task_status(data.get('task_id'), data.get('status'), strict=strict)
                return {"status": "success", "result": result}
                
            elif action == "get_tasks":
                result = await self.get_tasks(data.get('entity_id'), data.get('status'), strict=strict)
                return {"status": "success", "result": result}
                
            elif action == "store_document_metadata":
                result = await self.store_document_metadata(data, strict=strict)
                return {"status": "success", "result": result}
                
            elif action == "create_obligation":
                result = await self.create_obligation(data, strict=strict)
                return {"status": "success", "result": result}
                
            elif action == "create_authorization":
                result = await self.create_authorization(data, strict=strict)
                return {"status": "success", "result": result}
                
            elif action == "execute_query":
                # Handle raw SQL queries
                query = data.get('query')
                params = data.get('params', [])
                # Convert list to tuple but keep datetime objects for timestamp columns
                if params:
                    converted_params = []
                    for param in params:
                        # Keep datetime objects as-is for database timestamp columns
                        converted_params.append(param)
                    params_tuple = tuple(converted_params)
                else:
                    params_tuple = None
                    
                # Ensure connection before executing
                if not await self.ensure_database_connection(strict=strict):
                    if strict:
                        raise DatabaseUnavailableError("execute_query")
                    return {"status": "error", "message": "Database unavailable"}
                    
                result = await self.db_service.execute_query(query, params_tuple)
                return {"status": "success", "result": result}
                
            elif action == "execute_command":
                # Handle raw SQL commands (INSERT, UPDATE, DELETE)
                query = data.get('query')
                params = data.get('params', [])
                # Convert list to tuple but keep datetime objects for timestamp columns
                if params:
                    converted_params = []
                    for param in params:
                        # Keep datetime objects as-is for database timestamp columns
                        converted_params.append(param)
                    params_tuple = tuple(converted_params)
                else:
                    params_tuple = None
                    
                # Ensure connection before executing
                if not await self.ensure_database_connection(strict=strict):
                    if strict:
                        raise DatabaseUnavailableError("execute_command")
                    return {"status": "error", "message": "Database unavailable"}
                    
                result = await self.db_service.execute_command(query, params_tuple)
                return {"status": "success", "result": result}
                
            else:
                return {"status": "error", "message": f"Unknown action: {action}"}
                
        except DatabaseUnavailableError as e:
            self.logger.error(f"Database unavailable for {action}: {e}")
            return {"status": "error", "message": str(e), "error_type": "database_unavailable"}
        except (EntityNotFoundError, TaskNotFoundError) as e:
            self.logger.warning(f"Resource not found for {action}: {e}")
            return {"status": "error", "message": str(e), "error_type": "not_found"}
        except Exception as e:
            self.logger.error(f"Error handling message {action}: {e}")
            return {"status": "error", "message": str(e), "error_type": "internal_error"}
    
    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a database task"""
        task_type = task.get('type')
        strict = task.get('strict', self.default_strict_mode)
        
        if task_type == "entity_maintenance":
            return await self._entity_maintenance()
        elif task_type == "data_cleanup":
            return await self._data_cleanup()
        else:
            return {"status": "error", "message": f"Unknown task type: {task_type}"}
    
    # ============================================================================
    # ENTITY OPERATIONS (Enhanced with strict mode)
    # ============================================================================
    
    async def match_entity(
        self, 
        entity_name: str, 
        strict: bool = None
    ) -> Optional[Dict[str, Any]]:
        """
        Match entity by exact name (as specified in requirements)
        
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
            self.log_activity("Entity matching", {"entity_name": entity_name, "strict": strict})
            
            # Ensure database connection (lazy loading)
            if not await self.ensure_database_connection(strict=strict):
                # Database unavailable
                if strict:
                    raise DatabaseUnavailableError("match_entity")
                self.log_activity("Entity matching failed - no database connection", {"entity_name": entity_name})
                return None
            
            # Check cache first
            cache_key = f"entity_{entity_name.lower()}"
            if cache_key in self.entity_cache:
                cached_result = self.entity_cache[cache_key]
                if (datetime.utcnow() - cached_result['cached_at']).seconds < self.cache_ttl:
                    return cached_result['data']
            
            # Query database for exact match
            async with self.db_service.get_session() as session:
                result = await session.execute(
                    select(Entity).where(Entity.name == entity_name)
                )
                entity = result.scalar_one_or_none()
                
                if entity:
                    entity_data = {
                        'entity_id': entity.entity_id,
                        'name': entity.name,
                        'category': entity.category,
                        'contact_info': entity.contact_info,
                        'notes': entity.notes,
                        'created_at': entity.created_at.isoformat() if entity.created_at else None,
                        'updated_at': entity.updated_at.isoformat() if entity.updated_at else None
                    }
                    
                    # Cache the result
                    self.entity_cache[cache_key] = {
                        'data': entity_data,
                        'cached_at': datetime.utcnow()
                    }
                    
                    return entity_data
            
            return None
            
        except DatabaseUnavailableError:
            raise  # Re-raise if strict mode
        except Exception as e:
            self.logger.error(f"Error matching entity: {e}")
            if strict:
                raise
            return None
    
    async def create_entity(
        self, 
        entity_data: Dict[str, Any], 
        strict: bool = None
    ) -> Dict[str, Any]:
        """
        Create a new entity with auto-generated ID
        
        Args:
            entity_data: Entity information (name required)
            strict: If True, fail if DB unavailable. If False, create fallback ID.
        
        Returns:
            Created entity data
            
        Raises:
            DatabaseUnavailableError: If strict=True and database unavailable
            DuplicateEntityError: If entity with same name already exists
        """
        if strict is None:
            strict = self.default_strict_mode
            
        try:
            # Ensure database connection (lazy loading)
            if not await self.ensure_database_connection(strict=strict):
                # Database unavailable
                if strict:
                    raise DatabaseUnavailableError("create_entity")
                    
                # Graceful fallback - generate temporary ID
                entity_id = f"E{len(self.entity_cache) + 1:03d}"
                self.log_activity("Entity created without database", {
                    "entity_id": entity_id, 
                    "name": entity_data.get('name'),
                    "warning": "database_unavailable"
                })
                return {
                    "status": "success", 
                    "entity_id": entity_id,
                    "message": "Entity created (database unavailable - temporary ID)",
                    "warning": "database_unavailable"
                }
            
            # Check for duplicate entity (by name)
            existing = await self.match_entity(entity_data['name'], strict=False)
            if existing:
                raise DuplicateEntityError(entity_data['name'])
            
            # Generate entity ID (E001, E002, etc.)
            entity_id = await self._generate_entity_id()
            
            async with self.db_service.get_session() as session:
                entity = Entity(
                    entity_id=entity_id,
                    name=entity_data['name'],
                    category=entity_data.get('category'),
                    contact_info=entity_data.get('contact_info'),
                    notes=entity_data.get('notes'),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                session.add(entity)
                await session.commit()
                await session.refresh(entity)
                
                result = {
                    'entity_id': entity.entity_id,
                    'name': entity.name,
                    'category': entity.category,
                    'contact_info': entity.contact_info,
                    'notes': entity.notes,
                    'created_at': entity.created_at.isoformat(),
                    'updated_at': entity.updated_at.isoformat()
                }
                
                self.log_activity("Entity created", {"entity_id": entity_id, "name": entity_data['name']})
                
                # Clear cache
                self.entity_cache.clear()
                
                return result
            
        except (DatabaseUnavailableError, DuplicateEntityError):
            raise  # Re-raise these specific errors
        except Exception as e:
            self.logger.error(f"Error creating entity: {e}")
            if strict:
                raise
            # Return error details in non-strict mode
            return {
                "status": "error",
                "message": f"Failed to create entity: {str(e)}",
                "error_type": "creation_failed"
            }
    
    async def get_entity(
        self, 
        entity_id: str, 
        strict: bool = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get entity by ID
        
        Args:
            entity_id: Entity ID to retrieve
            strict: If True, raise errors on failure
        
        Returns:
            Entity data if found, None otherwise
            
        Raises:
            DatabaseUnavailableError: If strict=True and database unavailable
        """
        if strict is None:
            strict = self.default_strict_mode
            
        try:
            self.log_activity("Get entity", {"entity_id": entity_id})
            
            # Ensure database connection
            if not await self.ensure_database_connection(strict=strict):
                if strict:
                    raise DatabaseUnavailableError("get_entity")
                return None
            
            async with self.db_service.get_session() as session:
                result = await session.execute(
                    select(Entity).where(Entity.entity_id == entity_id)
                )
                entity = result.scalar_one_or_none()
                
                if entity:
                    return {
                        'entity_id': entity.entity_id,
                        'name': entity.name,
                        'category': entity.category,
                        'contact_info': entity.contact_info,
                        'notes': entity.notes,
                        'created_at': entity.created_at.isoformat() if entity.created_at else None,
                        'updated_at': entity.updated_at.isoformat() if entity.updated_at else None
                    }
                
                return None
            
        except DatabaseUnavailableError:
            raise
        except Exception as e:
            self.logger.error(f"Error getting entity: {e}")
            if strict:
                raise
            return None
    
    async def list_entities(self, strict: bool = None) -> List[Dict[str, Any]]:
        """
        List all entities
        
        Args:
            strict: If True, raise errors on failure
        
        Returns:
            List of entities (empty list if DB unavailable in non-strict mode)
            
        Raises:
            DatabaseUnavailableError: If strict=True and database unavailable
        """
        if strict is None:
            strict = self.default_strict_mode
            
        try:
            self.log_activity("List entities")
            
            # Ensure database connection
            if not await self.ensure_database_connection(strict=strict):
                if strict:
                    raise DatabaseUnavailableError("list_entities")
                return []
            
            async with self.db_service.get_session() as session:
                result = await session.execute(select(Entity).order_by(Entity.name))
                entities = result.scalars().all()
                
                return [
                    {
                        'entity_id': entity.entity_id,
                        'name': entity.name,
                        'category': entity.category,
                        'contact_info': entity.contact_info,
                        'notes': entity.notes,
                        'created_at': entity.created_at.isoformat() if entity.created_at else None,
                        'updated_at': entity.updated_at.isoformat() if entity.updated_at else None
                    }
                    for entity in entities
                ]
            
        except DatabaseUnavailableError:
            raise
        except Exception as e:
            self.logger.error(f"Error listing entities: {e}")
            if strict:
                raise
            return []
    
    # ============================================================================
    # TASK OPERATIONS (Enhanced with strict mode)
    # ============================================================================
    
    async def create_task(
        self, 
        task_data: Dict[str, Any], 
        strict: bool = None
    ) -> Dict[str, Any]:
        """Create a new task with auto-generated ID"""
        if strict is None:
            strict = self.default_strict_mode
            
        try:
            # Ensure database connection
            if not await self.ensure_database_connection(strict=strict):
                if strict:
                    raise DatabaseUnavailableError("create_task")
                return {
                    "status": "error",
                    "message": "Database unavailable",
                    "error_type": "database_unavailable"
                }
            
            # Generate task ID (T001, T002, etc.)
            task_id = await self._generate_task_id()
            
            async with self.db_service.get_session() as session:
                task = Task(
                    task_id=task_id,
                    description=task_data['description'],
                    type=task_data.get('type'),
                    entity_id=task_data.get('entity_id'),
                    due_date=task_data.get('due_date'),
                    frequency=Frequency(task_data['frequency']) if task_data.get('frequency') else None,
                    status=TaskStatus.PENDING,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                session.add(task)
                await session.commit()
                await session.refresh(task)
                
                result = {
                    'task_id': task.task_id,
                    'description': task.description,
                    'type': task.type,
                    'entity_id': task.entity_id,
                    'due_date': task.due_date.isoformat() if task.due_date else None,
                    'frequency': task.frequency.value if task.frequency else None,
                    'status': task.status.value,
                    'created_at': task.created_at.isoformat(),
                    'updated_at': task.updated_at.isoformat()
                }
                
                self.log_activity("Task created", {"task_id": task_id, "description": task_data['description']})
                
                return result
            
        except DatabaseUnavailableError:
            raise
        except Exception as e:
            self.logger.error(f"Error creating task: {e}")
            if strict:
                raise
            return {
                "status": "error",
                "message": f"Failed to create task: {str(e)}",
                "error_type": "creation_failed"
            }
    
    async def update_task_status(
        self, 
        task_id: str, 
        status: str, 
        strict: bool = None
    ) -> bool:
        """Update task status"""
        if strict is None:
            strict = self.default_strict_mode
            
        try:
            self.log_activity("Task status update", {"task_id": task_id, "status": status})
            
            # Ensure database connection
            if not await self.ensure_database_connection(strict=strict):
                if strict:
                    raise DatabaseUnavailableError("update_task_status")
                return False
            
            async with self.db_service.get_session() as session:
                result = await session.execute(
                    select(Task).where(Task.task_id == task_id)
                )
                task = result.scalar_one_or_none()
                
                if task:
                    task.status = TaskStatus(status)
                    task.updated_at = datetime.utcnow()
                    
                    if status == TaskStatus.DONE.value:
                        task.completed_at = datetime.utcnow()
                    
                    await session.commit()
                    return True
                
                if strict:
                    raise TaskNotFoundError(task_id)
                return False
            
        except (DatabaseUnavailableError, TaskNotFoundError):
            raise
        except Exception as e:
            self.logger.error(f"Error updating task status: {e}")
            if strict:
                raise
            return False
    
    async def get_tasks(
        self, 
        entity_id: Optional[str] = None, 
        status: Optional[str] = None,
        strict: bool = None
    ) -> List[Dict[str, Any]]:
        """Get tasks with optional filtering"""
        if strict is None:
            strict = self.default_strict_mode
            
        try:
            self.log_activity("Get tasks", {"entity_id": entity_id, "status": status})
            
            # Ensure database connection
            if not await self.ensure_database_connection(strict=strict):
                if strict:
                    raise DatabaseUnavailableError("get_tasks")
                return []
            
            async with self.db_service.get_session() as session:
                query = select(Task)
                
                if entity_id:
                    query = query.where(Task.entity_id == entity_id)
                
                if status:
                    query = query.where(Task.status == TaskStatus(status))
                
                query = query.order_by(Task.created_at.desc())
                
                result = await session.execute(query)
                tasks = result.scalars().all()
                
                return [
                    {
                        'task_id': task.task_id,
                        'description': task.description,
                        'type': task.type,
                        'entity_id': task.entity_id,
                        'due_date': task.due_date.isoformat() if task.due_date else None,
                        'frequency': task.frequency.value if task.frequency else None,
                        'status': task.status.value,
                        'created_at': task.created_at.isoformat() if task.created_at else None,
                        'updated_at': task.updated_at.isoformat() if task.updated_at else None,
                        'completed_at': task.completed_at.isoformat() if task.completed_at else None
                    }
                    for task in tasks
                ]
            
        except DatabaseUnavailableError:
            raise
        except Exception as e:
            self.logger.error(f"Error getting tasks: {e}")
            if strict:
                raise
            return []
    
    # ============================================================================
    # OBLIGATION OPERATIONS (Enhanced with strict mode)
    # ============================================================================
    
    async def create_obligation(
        self, 
        obligation_data: Dict[str, Any],
        strict: bool = None
    ) -> Dict[str, Any]:
        """Create a new obligation"""
        if strict is None:
            strict = self.default_strict_mode
            
        try:
            # Ensure database connection
            if not await self.ensure_database_connection(strict=strict):
                if strict:
                    raise DatabaseUnavailableError("create_obligation")
                return {
                    "status": "error",
                    "message": "Database unavailable",
                    "error_type": "database_unavailable"
                }
            
            obligation_id = await self._generate_obligation_id()
            
            async with self.db_service.get_session() as session:
                obligation = Obligation(
                    obligation_id=obligation_id,
                    description=obligation_data['description'],
                    entity_id=obligation_data.get('entity_id'),
                    frequency=Frequency(obligation_data['frequency']) if obligation_data.get('frequency') else None,
                    trigger_date=obligation_data.get('trigger_date'),
                    reminder_lead_time=obligation_data.get('reminder_lead_time', 5),
                    last_completed=obligation_data.get('last_completed'),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                session.add(obligation)
                await session.commit()
                await session.refresh(obligation)
                
                result = {
                    'obligation_id': obligation.obligation_id,
                    'description': obligation.description,
                    'entity_id': obligation.entity_id,
                    'frequency': obligation.frequency.value if obligation.frequency else None,
                    'trigger_date': obligation.trigger_date.isoformat() if obligation.trigger_date else None,
                    'reminder_lead_time': obligation.reminder_lead_time,
                    'last_completed': obligation.last_completed.isoformat() if obligation.last_completed else None,
                    'created_at': obligation.created_at.isoformat(),
                    'updated_at': obligation.updated_at.isoformat()
                }
                
                self.log_activity("Obligation created", {"obligation_id": obligation_id})
                
                return result
                
        except DatabaseUnavailableError:
            raise
        except Exception as e:
            self.logger.error(f"Error creating obligation: {e}")
            if strict:
                raise
            return {
                "status": "error",
                "message": f"Failed to create obligation: {str(e)}",
                "error_type": "creation_failed"
            }
    
    # ============================================================================
    # AUTHORIZATION OPERATIONS (Enhanced with strict mode)
    # ============================================================================
    
    async def create_authorization(
        self, 
        auth_data: Dict[str, Any],
        strict: bool = None
    ) -> Dict[str, Any]:
        """Create a new authorization"""
        if strict is None:
            strict = self.default_strict_mode
            
        try:
            # Ensure database connection
            if not await self.ensure_database_connection(strict=strict):
                if strict:
                    raise DatabaseUnavailableError("create_authorization")
                return {
                    "status": "error",
                    "message": "Database unavailable",
                    "error_type": "database_unavailable"
                }
            
            auth_id = await self._generate_authorization_id()
            
            async with self.db_service.get_session() as session:
                authorization = Authorization(
                    auth_id=auth_id,
                    entity_id=auth_data.get('entity_id'),
                    task_type=auth_data['task_type'],
                    author=auth_data['author'],
                    expiry=auth_data.get('expiry'),
                    slack_link=auth_data.get('slack_link'),
                    description=auth_data.get('description'),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                session.add(authorization)
                await session.commit()
                await session.refresh(authorization)
                
                result = {
                    'auth_id': authorization.auth_id,
                    'entity_id': authorization.entity_id,
                    'task_type': authorization.task_type,
                    'author': authorization.author,
                    'expiry': authorization.expiry.isoformat() if authorization.expiry else None,
                    'slack_link': authorization.slack_link,
                    'description': authorization.description,
                    'created_at': authorization.created_at.isoformat(),
                    'updated_at': authorization.updated_at.isoformat()
                }
                
                self.log_activity("Authorization created", {"auth_id": auth_id})
                
                return result
                
        except DatabaseUnavailableError:
            raise
        except Exception as e:
            self.logger.error(f"Error creating authorization: {e}")
            if strict:
                raise
            return {
                "status": "error",
                "message": f"Failed to create authorization: {str(e)}",
                "error_type": "creation_failed"
            }
    
    # ============================================================================
    # DOCUMENT METADATA OPERATIONS (Enhanced with strict mode)
    # ============================================================================
    
    async def store_document_metadata(
        self, 
        doc_data: Dict[str, Any],
        strict: bool = None
    ) -> Dict[str, Any]:
        """Store document metadata"""
        if strict is None:
            strict = self.default_strict_mode
            
        try:
            # Ensure database connection
            if not await self.ensure_database_connection(strict=strict):
                if strict:
                    raise DatabaseUnavailableError("store_document_metadata")
                return {
                    "status": "error",
                    "message": "Database unavailable",
                    "error_type": "database_unavailable"
                }
            
            doc_id = str(uuid.uuid4())
            
            async with self.db_service.get_session() as session:
                document = DocumentMetadata(
                    doc_id=doc_id,
                    file_name=doc_data['file_name'],
                    file_id=doc_data.get('file_id'),
                    entity_id=doc_data.get('entity_id'),
                    entity_name=doc_data.get('entity_name'),
                    issue_date=doc_data.get('issue_date'),
                    subject=doc_data.get('subject'),
                    summary=doc_data.get('summary'),
                    document_type=doc_data.get('document_type'),
                    drive_link=doc_data.get('drive_link'),
                    confidence_scores=json.dumps(doc_data.get('confidence_scores', {})),
                    processing_time=datetime.utcnow(),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                session.add(document)
                await session.commit()
                await session.refresh(document)
                
                result = {
                    'doc_id': document.doc_id,
                    'file_name': document.file_name,
                    'file_id': document.file_id,
                    'entity_id': document.entity_id,
                    'entity_name': document.entity_name,
                    'issue_date': document.issue_date.isoformat() if document.issue_date else None,
                    'subject': document.subject,
                    'summary': document.summary,
                    'document_type': document.document_type,
                    'drive_link': document.drive_link,
                    'confidence_scores': json.loads(document.confidence_scores) if document.confidence_scores else {},
                    'processing_time': document.processing_time.isoformat() if document.processing_time else None,
                    'created_at': document.created_at.isoformat(),
                    'updated_at': document.updated_at.isoformat()
                }
                
                self.log_activity("Document metadata stored", {"doc_id": doc_id, "file_name": doc_data['file_name']})
                
                return result
            
        except DatabaseUnavailableError:
            raise
        except Exception as e:
            self.logger.error(f"Error storing document metadata: {e}")
            if strict:
                raise
            return {
                "status": "error",
                "message": f"Failed to store document metadata: {str(e)}",
                "error_type": "storage_failed"
            }
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    async def _generate_entity_id(self) -> str:
        """Generate next entity ID (E001, E002, etc.)"""
        try:
            async with self.db_service.get_session() as session:
                result = await session.execute(
                    select(func.count(Entity.entity_id))
                )
                count = result.scalar()
                return f"E{str(count + 1).zfill(3)}"
        except Exception:
            # Fallback to random if query fails
            return f"E{str(uuid.uuid4().int)[:3].zfill(3)}"
    
    async def _generate_task_id(self) -> str:
        """Generate next task ID (T001, T002, etc.)"""
        try:
            async with self.db_service.get_session() as session:
                result = await session.execute(
                    select(func.count(Task.task_id))
                )
                count = result.scalar()
                return f"T{str(count + 1).zfill(3)}"
        except Exception:
            # Fallback to random if query fails
            return f"T{str(uuid.uuid4().int)[:3].zfill(3)}"
    
    async def _generate_obligation_id(self) -> str:
        """Generate next obligation ID (O001, O002, etc.)"""
        try:
            async with self.db_service.get_session() as session:
                result = await session.execute(
                    select(func.count(Obligation.obligation_id))
                )
                count = result.scalar()
                return f"O{str(count + 1).zfill(3)}"
        except Exception:
            # Fallback to random if query fails
            return f"O{str(uuid.uuid4().int)[:3].zfill(3)}"
    
    async def _generate_authorization_id(self) -> str:
        """Generate next authorization ID (A001, A002, etc.)"""
        try:
            async with self.db_service.get_session() as session:
                result = await session.execute(
                    select(func.count(Authorization.auth_id))
                )
                count = result.scalar()
                return f"A{str(count + 1).zfill(3)}"
        except Exception:
            # Fallback to random if query fails
            return f"A{str(uuid.uuid4().int)[:3].zfill(3)}"
    
    async def _entity_maintenance(self) -> Dict[str, Any]:
        """Perform entity maintenance tasks"""
        self.log_activity("Entity maintenance started")
        
        # Clear expired cache
        self.entity_cache.clear()
        
        # Additional maintenance tasks could be added here
        
        return {"status": "completed", "message": "Entity maintenance completed"}
    
    async def _data_cleanup(self) -> Dict[str, Any]:
        """Perform data cleanup tasks"""
        self.log_activity("Data cleanup started")
        
        # Cleanup logic would go here (e.g., remove old temp records)
        
        return {"status": "completed", "message": "Data cleanup completed"}
    
    def connect_agent(self, agent_type: str, agent_instance):
        """Connect to another agent (required by coordinator)"""
        # DBAgent doesn't need to connect to other agents directly
        pass
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check (required by coordinator)"""
        try:
            # Check database connection
            if await self.ensure_database_connection(strict=False):
                return {"status": "healthy", "message": "Database connection OK"}
            else:
                return {"status": "unhealthy", "message": "Database connection failed"}
        except Exception as e:
            return {"status": "unhealthy", "message": f"Health check failed: {e}"}