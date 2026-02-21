import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from src.config.env_config import ENV_CONFIG

DB_URL = ENV_CONFIG.DB_URL


async def test_connection():
    engine = create_async_engine(DB_URL, echo=True, connect_args={"statement_cache_size": 0})

    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            print("OK Connection successful! Result:", result.scalar())
    except Exception as e:
        print("FAILED Connection failed:", e)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(test_connection())
