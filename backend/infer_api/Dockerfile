FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    fastapi[all] \
    uvicorn[standard] \
    sqlalchemy[asyncio] \
    asyncpg \
    pydantic-settings \
    python-jose[cryptography] \
    passlib[bcrypt] \
    minio \
    redis \
    onnxruntime \
    opencv-python-headless \
    Pillow \
    numpy \
    prometheus-fastapi-instrumentator

COPY . .

EXPOSE 8002

CMD ["uvicorn", "infer_api.main:app", "--host", "0.0.0.0", "--port", "8002"]
