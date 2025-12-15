from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

import os
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DB_URL")

engine = create_async_engine(db_url)

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
