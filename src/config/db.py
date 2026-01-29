from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from  .env_config import ENV_CONFIG


db_url = ENV_CONFIG.DB_URL

engine = create_async_engine(
    db_url + "?sslmode=require",
    echo=True,
)

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
