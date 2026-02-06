# Stage 1: Builder
FROM python:3.12-slim-bookworm AS builder

# DL4006: Set pipefail to ensure curls/pipes fail correctly
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

# DL3008: Added specific versions (or just use -y for speed in builder)
# Note: In a builder, pinning is less critical, but Hadolint wants it.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential=12.9 \
    libpq-dev=15.10-0+deb12u1 \
    curl=7.88.1-10+deb12u8 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app
COPY pyproject.toml poetry.lock* ./

RUN poetry install --only main --no-root

# --- Stage 2: Final Runtime ---
FROM python:3.12-slim-bookworm

WORKDIR /app

# DL4006: Set pipefail here too
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# DL3013 & DL3042: Pin pip and use --no-cache-dir
RUN pip install --no-cache-dir --upgrade pip==26.0

# DL3008: Pin versions for production runtime stability
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    libpq5=15.10-0+deb12u1 \
    libmagic1=1:5.44-3 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . .

RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]