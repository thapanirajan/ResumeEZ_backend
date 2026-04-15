from fastapi import APIRouter
from pydantic import BaseModel
from src.services.groq_service import rewrite_summary

ollama_router = APIRouter(tags=["AI"])


class AIRequest(BaseModel):
    prompt: str


@ollama_router.post("/generate")
async def generate_text(request: AIRequest):
    response = await rewrite_summary(request.prompt)
    return {"result": response}
