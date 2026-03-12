# AI Assist service: SAM2 requires GPU for practical performance
FROM nvcr.io/nvidia/pytorch:24.03-py3

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    fastapi[all] \
    uvicorn[standard] \
    sqlalchemy[asyncio] \
    asyncpg \
    pydantic-settings \
    minio \
    redis \
    Pillow \
    numpy \
    transformers \
    accelerate

# Install SAM2 (from Meta)
RUN pip install --no-cache-dir "sam2 @ git+https://github.com/facebookresearch/segment-anything-2.git" || \
    echo "SAM2 not available, will run in degraded mode"

COPY . .

EXPOSE 8003

CMD ["uvicorn", "ai_assist.main:app", "--host", "0.0.0.0", "--port", "8003"]
