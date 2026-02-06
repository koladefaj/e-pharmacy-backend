# Stage 1: Builder
FROM python:3.12-slim AS builder

# Set build-time environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

# Install system-level build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app
COPY pyproject.toml poetry.lock* ./

# Install only production dependencies to the system path
RUN poetry install --only main --no-root

# --- Stage 2: Final Runtime ---
FROM python:3.12-slim

WORKDIR /app

# 1. Patch pip in the final stage to fix CVE-2025-8869 & CVE-2026-1703
RUN pip install --upgrade pip>=26.0

# 2. Install runtime system dependencies
RUN apt-get update && apt-get upgrade -y &&\ 
    apt-get install -y --no-install-recommends \
    libpq5 \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# 3. Copy python packages and binaries from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 4. Copy app code (excluding files in .dockerignore)
COPY . .

# 5. Security: Run as non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Start the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]