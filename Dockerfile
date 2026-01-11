# Build Stage
FROM python:3.11-slim as builder

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml poetry.lock ./
RUN pip install poetry && \
    poetry config virtualenvs.in-project true && \
    poetry install --only main --no-root

# Runtime Stage
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

RUN groupadd -g 1000 gaia && \
    useradd -u 1000 -g gaia -s /bin/bash -m gaia

COPY --from=builder --chown=gaia:gaia /app/.venv /app/.venv
COPY --chown=gaia:gaia src /app/src

USER gaia

CMD ["python", "src/main.py"]
