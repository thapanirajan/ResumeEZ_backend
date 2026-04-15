from src.services.groq_service import rewrite_summary


async def call_ollama(prompt: str) -> str:
    """Rewrite a resume summary using Groq (replaces local Ollama)."""
    return await rewrite_summary(prompt)
