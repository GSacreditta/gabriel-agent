"""Alembic migration env.

Reads the database URL from app settings (which in turn picks it up from env
vars / Secret Manager). Runs sync because Alembic itself is sync; we swap the
asyncpg driver for psycopg2 in the URL.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make `app` importable when running `alembic ...` from apps/svc/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import secrets  # noqa: E402

secrets.load_secrets_into_env()

from app.core.config import get_settings  # noqa: E402
from app.models import Base  # noqa: E402  # registers all model metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Compose the sync URL for Alembic from settings (swap asyncpg → psycopg2).
_settings = get_settings()
_async_url = _settings.database_url
_sync_url = _async_url.replace("+asyncpg", "+psycopg2")
config.set_main_option("sqlalchemy.url", _sync_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
