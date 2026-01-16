import asyncio
from logging.config import fileConfig

from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from alembic import context

from src.config.env_config import ENV
from src.config.base import Base
import src.models

# Alembic Config object
config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model metadata
target_metadata = Base.metadata

# Async database URL
DB_URL = ENV.DB_URL
if DB_URL is None:
    raise ValueError("DB_URL not found in environment variables")
config.set_main_option("sqlalchemy.url", DB_URL)

# ------------------------------
# Offline migrations (no DB connection)
# ------------------------------
def run_migrations_offline() -> None:
    url = DB_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# ------------------------------
# Online migrations (async)
# ------------------------------
async def run_async_migrations():
    connectable: AsyncEngine = create_async_engine(
        DB_URL,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    asyncio.run(run_async_migrations())


# ------------------------------
# Run Alembic
# ------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
