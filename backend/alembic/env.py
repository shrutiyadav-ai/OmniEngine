"""
OmniEngine — Alembic Environment Configuration

Configures Alembic to use async SQLAlchemy with the application's models
and database URL from environment variables.
"""

import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so we can import backend modules
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# ---------------------------------------------------------------------------
# Alembic Config object — provides access to values within alembic.ini
# ---------------------------------------------------------------------------
config = context.config

# Setup Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Import all ORM models so Alembic can detect them for --autogenerate
# ---------------------------------------------------------------------------
from backend.memory.models import Base  # noqa: E402

target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# Override database URL from environment variable if available
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    # Alembic requires the sync driver for offline mode but async for online.
    # We store both variants.
    config.set_main_option("sqlalchemy.url", DATABASE_URL)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Generates SQL scripts without connecting to the database. Useful for
    reviewing migration SQL before applying it.

    Usage: alembic upgrade head --sql
    """
    url = config.get_main_option("sqlalchemy.url")

    # For offline mode, convert async URL to sync
    if url and "+asyncpg" in url:
        url = url.replace("+asyncpg", "+psycopg2")

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
    """Execute migrations within an active connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        render_as_batch=True,  # Support for SQLite batch operations if needed
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode using async engine.

    Creates an async Engine and associates a connection with the context.
    """
    configuration = config.get_section(config.config_ini_section, {})

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations — delegates to async runner."""
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Determine migration mode and execute
# ---------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
