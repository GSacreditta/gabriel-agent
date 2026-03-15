"""
Database Service - Manages database connections and operations
Enhanced version with fallback connection logic

This version attempts Cloud SQL Unix socket connection first,
then falls back to public IP connection if Unix socket fails.
This provides better resilience in development and misconfigured environments.
"""

import os
import logging
from typing import AsyncGenerator, Optional, Tuple, List, Dict, Any
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, create_async_engine, async_sessionmaker
from sqlalchemy import text

from ...models.database_models import Base

logger = logging.getLogger(__name__)


class DatabaseService:
    """Async database service with connection pooling and fallback logic"""
    
    def __init__(self):
        self.engine: Optional[AsyncEngine] = None
        self.session_maker: Optional[async_sessionmaker] = None
        self._initialized = False
        self.connection_type: str = "unknown"
    
    async def initialize(self) -> bool:
        """
        Initialize database connection with fallback support.
        
        Connection priority:
        1. Cloud SQL Unix socket (if DB_CONNECTION_NAME is set)
        2. Fallback to public IP connection (if Unix socket fails)
        
        Returns:
            bool: True if connection established, False otherwise
        """
        try:
            # Get database credentials from environment
            db_host = os.getenv('DB_HOST', 'localhost')
            db_port = os.getenv('DB_PORT', '5432')
            db_name = os.getenv('DB_NAME', 'gabriel_agent')
            db_user = os.getenv('DB_USER', 'postgres')
            db_password = os.getenv('DB_PASSWORD', '')
            
            # Check for Cloud SQL connection name
            db_connection_name = os.getenv('DB_CONNECTION_NAME')
            
            # Attempt 1: Cloud SQL Unix Socket Connection (Production)
            if db_connection_name:
                if await self._try_unix_socket_connection(
                    db_connection_name, db_user, db_password, db_name
                ):
                    return True
                
                logger.warning("⚠️ Unix socket connection failed, attempting public IP fallback...")
            
            # Attempt 2: Public IP Connection (Fallback/Development)
            return await self._try_public_ip_connection(
                db_host, db_port, db_user, db_password, db_name
            )
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize database service: {e}")
            logger.exception("Full traceback:")
            self.engine = None
            self.session_maker = None
            self._initialized = False
            return False
    
    async def _try_unix_socket_connection(
        self,
        connection_name: str,
        user: str,
        password: str,
        db_name: str
    ) -> bool:
        """
        Attempt to connect via Cloud SQL Unix socket.
        
        Args:
            connection_name: Cloud SQL connection name (project:region:instance)
            user: Database user
            password: Database password
            db_name: Database name
            
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            logger.info(f"🔌 Attempting Cloud SQL Unix socket connection: {connection_name}")
            
            # Build Unix socket connection string
            connection_string = (
                f"postgresql+asyncpg://{user}:{password}@/{db_name}"
                f"?host=/cloudsql/{connection_name}"
            )
            
            # Create async engine
            engine = create_async_engine(
                connection_string,
                echo=False,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                pool_recycle=3600,
                connect_args={
                    "timeout": 10,  # Connection timeout
                    "command_timeout": 10,  # Command timeout
                }
            )
            
            # Test connection
            async with engine.begin() as conn:
                result = await conn.execute(text("SELECT 1 as test"))
                row = result.fetchone()
                if row and row[0] == 1:
                    logger.info("✅ Unix socket connection test successful")
                else:
                    raise Exception("Connection test query returned unexpected result")
            
            # Success! Set instance variables
            self.engine = engine
            self.connection_type = "unix_socket"
            
            # Create session maker
            self.session_maker = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            self._initialized = True
            logger.info(f"✅ Database service initialized successfully via Unix socket")
            logger.info(f"   Connection: /cloudsql/{connection_name}")
            
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ Unix socket connection failed: {type(e).__name__}: {e}")
            # Clean up failed engine
            if 'engine' in locals():
                try:
                    await engine.dispose()
                except:
                    pass
            return False
    
    async def _try_public_ip_connection(
        self,
        host: str,
        port: str,
        user: str,
        password: str,
        db_name: str
    ) -> bool:
        """
        Attempt to connect via public IP/TCP connection.
        
        Args:
            host: Database host (IP or hostname)
            port: Database port
            user: Database user
            password: Database password
            db_name: Database name
            
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            logger.info(f"🔌 Attempting public IP connection: {host}:{port}/{db_name}")
            
            # Build public IP connection string
            connection_string = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db_name}"
            
            # Create async engine
            engine = create_async_engine(
                connection_string,
                echo=False,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                pool_recycle=3600,
                connect_args={
                    "timeout": 10,  # Connection timeout
                    "command_timeout": 10,  # Command timeout
                }
            )
            
            # Test connection
            async with engine.begin() as conn:
                result = await conn.execute(text("SELECT 1 as test"))
                row = result.fetchone()
                if row and row[0] == 1:
                    logger.info("✅ Public IP connection test successful")
                else:
                    raise Exception("Connection test query returned unexpected result")
            
            # Success! Set instance variables
            self.engine = engine
            self.connection_type = "public_ip"
            
            # Create session maker
            self.session_maker = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            self._initialized = True
            logger.info(f"✅ Database service initialized successfully via public IP")
            logger.info(f"   Connection: {host}:{port}/{db_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Public IP connection failed: {type(e).__name__}: {e}")
            logger.exception("Full traceback:")
            # Clean up failed engine
            if 'engine' in locals():
                try:
                    await engine.dispose()
                except:
                    pass
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
            logger.info(f"Database service closed (was using {self.connection_type})")
    
    @property
    def is_initialized(self) -> bool:
        """Check if database service is initialized"""
        return self._initialized
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information for debugging"""
        return {
            "initialized": self._initialized,
            "connection_type": self.connection_type,
            "has_engine": self.engine is not None,
            "has_session_maker": self.session_maker is not None,
        }


# Singleton instance
_database_service: Optional[DatabaseService] = None


async def get_database_service() -> DatabaseService:
    """Get or create database service singleton"""
    global _database_service
    
    if _database_service is None:
        _database_service = DatabaseService()
        await _database_service.initialize()
    
    return _database_service


async def reset_database_service():
    """Reset database service (useful for testing or reconnection)"""
    global _database_service
    
    if _database_service is not None:
        await _database_service.close()
        _database_service = None
    
    logger.info("Database service reset")
