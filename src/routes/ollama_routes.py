

from fastapi import APIRouter
from pydantic import BaseModel
from src.services.ollama_service import call_ollama

ollama_router = APIRouter(tags=["ollama"])

class AIRequest(BaseModel):
    prompt: str


@ollama_router.post("/generate")
async def generate_text(request: AIRequest):
    response = await call_ollama(request.prompt)
    return {"result": response}
