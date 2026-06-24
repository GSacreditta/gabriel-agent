"""Alembic environment configuration for async PostgreSQL migrations."""

import asyncio
import os
from logging.config import fileConfig
from urllib.parse import quote_plus

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Load environment variables
from dotenv import load_dotenv

load_dotenv()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import models for autogenerate support
from app.models.database_models import Base

target_metadata = Base.metadata

# Build database URL from environment variables
def get_database_url() -> str:
    """Construct database URL from environment variables."""
    import platform
    
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT", "5432")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_name = os.getenv("DB_NAME")
    db_connection_name = os.getenv("DB_CONNECTION_NAME")

    if not all([db_user, db_password, db_name]):
        raise ValueError(
            "Missing required database environment variables: DB_USER, DB_PASSWORD, DB_NAME"
        )

    # URL-encode credentials
    db_password_encoded = quote_plus(str(db_password))
    db_user_encoded = quote_plus(str(db_user))

    # On Windows, Unix sockets don't work, so always use direct connection
    # In Cloud Run (Linux), use Unix socket if DB_CONNECTION_NAME is set
    is_windows = platform.system() == "Windows"
    
    if db_connection_name and not is_windows:
        # Cloud SQL using Unix socket (Linux only)
        url = f"postgresql+asyncpg://{db_user_encoded}:{db_password_encoded}@/{db_name}?host=/cloudsql/{db_connection_name}"
    else:
        # Standard PostgreSQL connection (Windows local dev or direct Cloud SQL)
        if not db_host:
            raise ValueError("DB_HOST required for direct PostgreSQL connections")
        url = f"postgresql+asyncpg://{db_user_encoded}:{db_password_encoded}@{db_host}:{db_port}/{db_name}"

    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async support."""
    # Build configuration dict with database URL
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()
    
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
