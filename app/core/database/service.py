"""
Database Service - Manages database connections and operations
"""

import os
import logging
from typing import AsyncGenerator, Optional, Tuple, List, Dict, Any
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, create_async_engine, async_sessionmaker
from sqlalchemy import text

from ...models.database_models import Base
from ..config import get_settings

logger = logging.getLogger(__name__)


class DatabaseService:
    """Async database service with connection pooling"""
    
    def __init__(self):
        self.engine: Optional[AsyncEngine] = None
        self.session_maker: Optional[async_sessionmaker] = None
        self._initialized = False
    
    async def initialize(self) -> bool:
        """Initialize database connection"""
        try:
            # Get settings (which may include secrets from Secret Manager)
            settings = get_settings()
            
            # Use settings instead of direct environment variables
            from urllib.parse import quote_plus
            
            db_host = settings.DB_HOST
            db_port = settings.DB_PORT
            db_name = settings.DB_NAME
            db_user = settings.DB_USER
            db_password = settings.DB_PASSWORD.get_secret_value() if hasattr(settings.DB_PASSWORD, 'get_secret_value') else str(settings.DB_PASSWORD)
            db_connection_name = settings.DB_CONNECTION_NAME
            
            # Log configuration (without exposing password)
            logger.info(f"Database config - Host: {db_host}, Port: {db_port}, DB: {db_name}, User: {db_user}, "
                       f"Connection Name: {db_connection_name}, Password length: {len(str(db_password))}")
            logger.debug(f"DB_HOST from env: {os.environ.get('DB_HOST', 'NOT SET')}")
            logger.debug(f"DB_USER from env: {os.environ.get('DB_USER', 'NOT SET')}")
            logger.debug(f"DB_NAME from env: {os.environ.get('DB_NAME', 'NOT SET')}")
            logger.debug(f"USE_SECRET_MANAGER: {os.environ.get('USE_SECRET_MANAGER', 'NOT SET')}")
            
            # URL-encode password to handle special characters like @
            db_password_encoded = quote_plus(str(db_password))
            db_user_encoded = quote_plus(str(db_user))
            
            if db_connection_name:
                # Cloud SQL using Unix socket
                connection_string = f"postgresql+asyncpg://{db_user_encoded}:{db_password_encoded}@/{db_name}?host=/cloudsql/{db_connection_name}"
                logger.info(f"Using Cloud SQL connection: {db_connection_name}")
            else:
                # Standard PostgreSQL connection
                connection_string = f"postgresql+asyncpg://{db_user_encoded}:{db_password_encoded}@{db_host}:{db_port}/{db_name}"
                logger.info(f"Using PostgreSQL connection: {db_host}:{db_port}/{db_name}")
            
            # Create async engine with connection pooling
            self.engine = create_async_engine(
                connection_string,
                echo=False,  # Set to True for SQL logging
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,  # Verify connections before using
                pool_recycle=3600  # Recycle connections after 1 hour
            )
            
            # Create session maker
            self.session_maker = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Test connection
            async with self.engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            
            self._initialized = True
            logger.info("✅ Database service initialized successfully")
            return True
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"❌ Failed to initialize database service: {e}")
            logger.error(f"Error details: {error_details}")
            logger.error(f"Connection config - Host: {db_host if 'db_host' in locals() else 'N/A'}, "
                        f"Port: {db_port if 'db_port' in locals() else 'N/A'}, "
                        f"DB: {db_name if 'db_name' in locals() else 'N/A'}, "
                        f"User: {db_user if 'db_user' in locals() else 'N/A'}, "
                        f"Connection Name: {db_connection_name if 'db_connection_name' in locals() else 'N/A'}")
            self.engine = None
            self.session_maker = None
            self._initialized = False
            return False
    
    async def create_tables(self):
        """Create all tables defined in models"""
        if not self.engine:
            raise RuntimeError("Database engine not initialized")
        
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Database tables created successfully")
        except Exception as e:
            logger.error(f"❌ Failed to create database tables: {e}")
            raise
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get async database session with automatic cleanup"""
        if not self.session_maker:
            raise RuntimeError("Database service not initialized")
        
        session = self.session_maker()
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()
    
    async def execute_query(self, query: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return results"""
        if not self.session_maker:
            raise RuntimeError("Database service not initialized")
        
        async with self.get_session() as session:
            result = await session.execute(text(query), params)
            return [dict(row._mapping) for row in result.fetchall()]
    
    async def execute_command(self, query: str, params: Optional[Tuple] = None) -> int:
        """Execute an INSERT/UPDATE/DELETE command and return affected rows"""
        if not self.session_maker:
            raise RuntimeError("Database service not initialized")
        
        async with self.get_session() as session:
            result = await session.execute(text(query), params)
            await session.commit()
            return result.rowcount
    
    async def close(self):
        """Close database connections"""
        if self.engine:
            await self.engine.dispose()
            self._initialized = False
            logger.info("Database service closed")
    
    @property
    def is_initialized(self) -> bool:
        """Check if database service is initialized"""
        return self._initialized


# Singleton instance
_database_service: Optional[DatabaseService] = None


async def get_database_service() -> DatabaseService:
    """Get or create database service singleton"""
    global _database_service
    
    if _database_service is None:
        _database_service = DatabaseService()
        await _database_service.initialize()
    
    return _database_service
