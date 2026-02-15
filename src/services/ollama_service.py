import httpx

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen3:8b"


async def call_ollama(prompt: str) -> str:
    prompt = f"""
    You are an expert executive resume editor.

    Rewrite the following resume summary to make it more professional, polished, and impactful.

    Requirements:
    - Preserve the original meaning.
    - Improve clarity and wording.
    - Use stronger action-oriented language.
    - Remove repetition.
    - Keep it concise (80–120 words).
    - Write in one single paragraph.
    - No markdown.
    - No bullet points.
    - Return ONLY the improved version.

    Original Summary:
    {prompt}
    """

    print("------------Prompt--------------")
    print(prompt)

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False
            }
        )
        response.raise_for_status()
        return response.json()["response"]
