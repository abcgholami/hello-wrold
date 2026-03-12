FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir uv && \
    uv pip install --system \
    fastapi[all] \
    uvicorn[standard] \
    sqlalchemy[asyncio] \
    asyncpg \
    alembic \
    pydantic-settings \
    python-jose[cryptography] \
    passlib[bcrypt] \
    minio \
    Pillow \
    imagehash \
    prometheus-fastapi-instrumentator \
    redis \
    celery \
    pyyaml

COPY . .

EXPOSE 8000

CMD ["uvicorn", "core_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
