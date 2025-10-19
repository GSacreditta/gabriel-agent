"""
Custom exceptions for Gabriel Agent system
"""


class GabrielAgentException(Exception):
    """Base exception for all Gabriel Agent errors"""
    pass


class DatabaseException(GabrielAgentException):
    """Base exception for database-related errors"""
    pass


class DatabaseUnavailableError(DatabaseException):
    """Raised when database service is unavailable and strict mode is enabled"""
    
    def __init__(self, operation: str = None, message: str = None):
        self.operation = operation
        if message is None:
            message = f"Database service unavailable for operation: {operation}" if operation else "Database service unavailable"
        super().__init__(message)


class DatabaseConnectionError(DatabaseException):
    """Raised when database connection fails"""
    
    def __init__(self, message: str = None, original_error: Exception = None):
        self.original_error = original_error
        if message is None:
            message = f"Failed to establish database connection: {original_error}" if original_error else "Database connection failed"
        super().__init__(message)


class EntityNotFoundError(DatabaseException):
    """Raised when an entity is not found in the database"""
    
    def __init__(self, entity_id: str = None, entity_name: str = None):
        self.entity_id = entity_id
        self.entity_name = entity_name
        message = f"Entity not found: {entity_id or entity_name}"
        super().__init__(message)


class TaskNotFoundError(DatabaseException):
    """Raised when a task is not found in the database"""
    
    def __init__(self, task_id: str):
        self.task_id = task_id
        super().__init__(f"Task not found: {task_id}")


class DuplicateEntityError(DatabaseException):
    """Raised when attempting to create a duplicate entity"""
    
    def __init__(self, entity_name: str):
        self.entity_name = entity_name
        super().__init__(f"Entity already exists: {entity_name}")


class InvalidOperationError(GabrielAgentException):
    """Raised when an invalid operation is attempted"""
    pass


class ServiceUnavailableError(GabrielAgentException):
    """Raised when a required service is unavailable"""
    
    def __init__(self, service_name: str, operation: str = None):
        self.service_name = service_name
        self.operation = operation
        message = f"Service '{service_name}' unavailable"
        if operation:
            message += f" for operation: {operation}"
        super().__init__(message)
