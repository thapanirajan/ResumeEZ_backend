from contextlib import asynccontextmanager
from fastapi import FastAPI

from src.config.base import Base
from src.config.db import engine

import src.models
# from src.routes.jobs_routes import recruiter_router
from src.routes.user_routes import user_router
from src.routes.upload_routes import upload_router
from src.utils.exceptions import AppException
from src.utils.error_handler import app_exception_handler

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# handles custom error
app.add_exception_handler(AppException, app_exception_handler)


@app.get("/")
async def root():
    return RedirectResponse("/docs")


# routes
app.include_router(user_router, prefix="/api/user")
# app.include_router(recruiter_router, prefix="/api/recruiter")
app.include_router(upload_router, prefix="/api/upload")
