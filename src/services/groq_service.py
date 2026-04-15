"""
Groq API service — drop-in replacement for Ollama calls.
Uses llama-3.3-70b-versatile (free tier, fast inference).
"""

import os
from groq import AsyncGroq

_GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

_client: AsyncGroq | None = None


def _get_client() -> AsyncGroq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set in environment variables")
        _client = AsyncGroq(api_key=api_key)
    return _client


async def call_groq(prompt: str, system_prompt: str | None = None, json_mode: bool = False) -> str:
    """Send a prompt to Groq and return the text response."""
    client = _get_client()

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    kwargs = dict(
        model=_GROQ_MODEL,
        messages=messages,
        temperature=0.3,
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = await client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


async def rewrite_summary(summary: str) -> str:
    """Rewrite a resume summary to be more professional (replaces ollama_service.call_ollama)."""
    system = (
        "You are an expert executive resume editor. "
        "Return ONLY the improved summary — no markdown, no bullet points, no explanation."
    )
    prompt = f"""Rewrite this resume summary to be more professional, polished, and impactful.

Requirements:
- Preserve the original meaning
- Improve clarity and wording
- Use stronger action-oriented language
- Remove repetition
- Keep it concise (80-120 words)
- Write in one single paragraph

Original Summary:
{summary}"""

    return await call_groq(prompt, system_prompt=system)


async def extract_resume_json(raw_text: str) -> str:
    """
    Extract structured resume data from raw text.
    Returns a JSON string matching the ResumeData schema.
    Uses Groq JSON mode to guarantee valid JSON output.
    """
    system = (
        "You are a resume parser that outputs ONLY a JSON object. "
        "Never include explanations, markdown, or extra text — just the JSON."
    )
    prompt = f"""Parse the resume below and return a JSON object with exactly these keys:

name, title, email, phone, location, linkedin, github, summary,
experience (array of objects with: company, role, startDate, endDate, description),
education (array of objects with: institution, degree, fieldOfStudy, startDate, endDate, gpa, honors),
projects (array of objects with: name, role, techStack, description, liveUrl, githubUrl),
skills (array of objects with: category, items)

Rules:
- All dates → YYYY-MM format (e.g. "2022-06") or "Present"
- skills.items → comma-separated string (e.g. "Python, React, Docker")
- Missing fields → empty string ""
- linkedin and github → full URL if found

Resume:
{raw_text}"""

    return await call_groq(prompt, system_prompt=system, json_mode=True)
