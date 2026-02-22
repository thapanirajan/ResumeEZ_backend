from contextlib import asynccontextmanager
from fastapi import FastAPI

from src.routes.candidate_dashboard_routes import candidate_dashbaord_router
from src.config.base import Base
from src.config.db import engine

import src.models
from src.routes.ollama_routes import ollama_router
from src.routes.resume_routes import resume_builder_router
from src.routes.user_routes import user_router
from src.routes.upload_routes import upload_router
from src.utils.exceptions import AppException
from src.utils.error_handler import app_exception_handler

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all DB tables
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
        "https://resume-ez-frontend-z32r.vercel.app",
        "https://resume-ez-frontend.vercel.app",
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


# ------------------------------- routes --------------------------------
app.include_router(user_router, prefix="/api/user")
app.include_router(upload_router, prefix="/api/upload")
app.include_router(resume_builder_router, prefix="/api/resume")
app.include_router(candidate_dashbaord_router, prefix="/api/candidate/dashboard")
app.include_router(ollama_router, prefix="/api/ollama")
