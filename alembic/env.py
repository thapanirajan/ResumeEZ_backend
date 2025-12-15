import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")

from src.config.base import Base  # your shared Base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DB_URL")
import src.models

# this is the Alembic Config object
config = context.config

fileConfig(config.config_file_name)

target_metadata = Base.metadata  # Alembic uses this for autogenerate


def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    """Run migrations in 'online' mode."""
    connectable = create_async_engine(DATABASE_URL, poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
