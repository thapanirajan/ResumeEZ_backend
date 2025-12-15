from contextlib import asynccontextmanager
from fastapi import FastAPI

from src.config.base import Base
from src.config.db import engine

import src.models
from src.routes.user_routes import user_router
from src.utils.exceptions import AppException
from src.utils.error_handler import app_exception_handler


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)

# handles custom error
app.add_exception_handler(AppException, app_exception_handler)

# routes

app.include_router(user_router, prefix="/api/user")
