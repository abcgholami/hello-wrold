FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    git \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (CPU-only PyTorch for build; GPU workers use Dockerfile.gpu)
RUN pip install --no-cache-dir \
    fastapi[all] \
    uvicorn[standard] \
    sqlalchemy[asyncio] \
    asyncpg \
    pydantic-settings \
    python-jose[cryptography] \
    passlib[bcrypt] \
    minio \
    celery[redis] \
    redis \
    prometheus-fastapi-instrumentator \
    mlflow \
    pyyaml \
    albumentations \
    Pillow \
    opencv-python-headless

COPY . .

EXPOSE 8001

CMD ["uvicorn", "train_api.main:app", "--host", "0.0.0.0", "--port", "8001"]
