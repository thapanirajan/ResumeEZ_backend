# ── Build stage: install dependencies ────────────────────────────────────────
FROM python:3.13-slim AS builder

# Copy uv binary from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# System libs required by spaCy (libgomp), psycopg2 (libpq), etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libgomp1 \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cached layer — re-run only when lock file changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Download the spaCy English model into the venv
RUN uv run python -m spacy download en_core_web_sm

# ── Final stage ───────────────────────────────────────────────────────────────
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Bring the pre-built venv from the builder
COPY --from=builder /app/.venv /app/.venv

# Copy application source
COPY . .

EXPOSE 8000

# uv run uses the existing .venv
CMD ["uv", "run", "python", "main.py"]
