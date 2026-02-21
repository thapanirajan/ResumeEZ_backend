from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from  .env_config import ENV_CONFIG


db_url = ENV_CONFIG.DB_URL

engine = create_async_engine(
    db_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={"statement_cache_size": 0},
)

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
