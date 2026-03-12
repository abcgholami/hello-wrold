# VisionForge

A full-stack, no-code machine vision platform. Upload images, label them, train a model, and run inference — all through a browser. Supports image classification, object detection, instance segmentation, and semantic segmentation.

---

## Architecture

```
Browser (React + TypeScript)
        │ REST + WebSocket
   Nginx Gateway (:80)
   ┌────┴──────────────────────┐
core_api  train_api  infer_api  ai_assist
 :8000     :8001      :8002      :8003
        │
PostgreSQL · Redis · MinIO · MLflow
```

| Service | Role |
|---|---|
| **core_api** | Projects, datasets, images, annotations, exports |
| **train_api** | Training jobs, model registry, Celery GPU worker |
| **infer_api** | REST/WebSocket inference, ONNX runtime, tracking |
| **ai_assist** | SAM2 auto-segmentation, CLIP classification hints |
| **workflow_engine** | No-code node graph execution (ReactFlow + asyncio) |

---

## Requirements

| Requirement | Details |
|---|---|
| **Docker Desktop** | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) — Windows, macOS, or Linux |
| **WSL 2** (Windows only) | Enabled automatically by Docker Desktop installer |
| **NVIDIA GPU** *(optional)* | Required only for training large models and SAM2 |
| **CUDA drivers** *(optional)* | [developer.nvidia.com/cuda-downloads](https://developer.nvidia.com/cuda-downloads) |

No Python, Node.js, or any other toolchain needs to be installed on the host — everything runs inside containers.

---

## Installation

### 1. Clone the repository

```bash
git clone <repo-url>
cd hello-wrold
```

### 2. Create the environment file

```bash
# Linux / macOS / Git Bash
cp .env.example .env

# Windows PowerShell
copy .env.example .env
```

The defaults in `.env.example` work for local development without any edits. For production, change `JWT_SECRET` to a strong random value:

```bash
# Generate a secure secret (Linux/macOS)
openssl rand -hex 32
```

### 3. Start all services

**CPU only (default):**
```bash
docker compose -f infra/docker-compose.yml up -d
```

**With GPU support for training:**
```bash
docker compose -f infra/docker-compose.yml --profile gpu up -d
```

**Using Make (Linux/macOS):**
```bash
make up        # CPU
make up-gpu    # GPU
```

Wait about 60 seconds for all services to become healthy, then open **http://localhost**.

### 4. Run database migrations

On first start, initialise the database schema:

```bash
docker compose -f infra/docker-compose.yml exec core_api alembic upgrade head

# Or with Make:
make migrate
```

---

## Accessing the Platform

| Interface | URL | Credentials |
|---|---|---|
| **Main UI** | http://localhost | — |
| **Frontend (dev server)** | http://localhost:3000 | — |
| **MinIO console** | http://localhost:9001 | `visionforge` / `visionforge_secret` |
| **MLflow** | http://localhost:5000 | — |
| **Grafana** | http://localhost:3001 | `admin` / `admin` |
| **Prometheus** | http://localhost:9090 | — |
| Core API docs (Swagger) | http://localhost:8000/docs | — |
| Train API docs | http://localhost:8001/docs | — |
| Infer API docs | http://localhost:8002/docs | — |

---

## Quick Start: Label → Train → Infer

1. **Register** — open http://localhost and create an account
2. **Create a project** — choose task type (detection, classification, segmentation)
3. **Upload images** — drag-and-drop images or a ZIP file
4. **Annotate** — draw bounding boxes or polygons; use the SAM2 auto-segment button for one-click masks
5. **Create a dataset version** — configure train/val/test split and optional augmentations
6. **Train** — select an architecture (e.g. YOLOv8n), choose a preset (Fast / Balanced / Accuracy), and launch
7. **Monitor training** — live loss and mAP charts stream in real time via WebSocket
8. **Evaluate** — view confusion matrix, per-class metrics, and browse false positives
9. **Deploy** — create an inference endpoint; test it via REST or WebSocket streaming

---

## Common Commands

```bash
# View all running services
docker compose -f infra/docker-compose.yml ps

# Follow logs for a service
docker compose -f infra/docker-compose.yml logs -f core_api
docker compose -f infra/docker-compose.yml logs -f celery_worker

# Open a shell inside the core API container
docker compose -f infra/docker-compose.yml exec core_api bash

# Open a PostgreSQL shell
docker compose -f infra/docker-compose.yml exec postgres psql -U visionforge visionforge

# Stop all services (data is preserved)
docker compose -f infra/docker-compose.yml down

# Stop and delete all data (full reset)
docker compose -f infra/docker-compose.yml down -v
```

With Make installed:

```bash
make help           # List all available commands
make up             # Start services
make down           # Stop services
make logs           # Follow all logs
make migrate        # Run DB migrations
make test           # Run backend tests
make lint           # Run linters
make build          # Rebuild Docker images
make clean          # Stop and remove all volumes
```

---

## Project Structure

```
hello-wrold/
├── frontend/                  # React 18 + TypeScript + Vite
│   └── src/
│       ├── pages/             # Route-level page components
│       ├── components/
│       │   ├── canvas/        # react-konva annotation editor
│       │   ├── charts/        # Recharts training/eval charts
│       │   ├── workflow-nodes/# ReactFlow custom node types
│       │   └── ui/            # Shared UI components
│       ├── store/             # Zustand state (auth, annotations)
│       ├── hooks/             # useWebSocket, useDebounce, etc.
│       └── api/               # Axios API clients
│
├── backend/
│   ├── core_api/              # FastAPI — projects, datasets, images, annotations
│   ├── train_api/             # FastAPI + Celery — training jobs, model registry
│   ├── infer_api/             # FastAPI — ONNX inference, ByteTrack, WebSocket stream
│   │   ├── engines/           # ONNXEngine, PyTorchEngine, TritonClient
│   │   └── postprocessing/    # NMS, tracker, annotation rendering
│   ├── ai_assist/             # SAM2 segmentation, CLIP classification hints
│   ├── workflow_engine/       # Async DAG executor + 20 node types
│   └── shared/                # SQLAlchemy models, JWT auth, Pydantic config
│
├── infra/
│   ├── docker-compose.yml     # Full local stack
│   ├── docker-compose.gpu.yml # GPU override
│   ├── nginx/                 # Reverse proxy config
│   └── monitoring/            # Prometheus scrape config, Grafana
│
├── sdks/
│   ├── python-sdk/            # pip install visionforge
│   └── js-sdk/                # npm install @visionforge/sdk
│
├── .env.example               # Environment variable template
└── Makefile                   # Developer shortcuts
```

---

## Supported Tasks and Models

| Task | Frameworks | Architectures |
|---|---|---|
| **Object Detection** | Ultralytics YOLO | YOLOv8 n/s/m/l/x, YOLOv9, YOLOv10, RT-DETR |
| **Image Classification** | Ultralytics + timm | YOLOv8-cls, ResNet-50, EfficientNetV2, ViT-B/16 |
| **Instance Segmentation** | Ultralytics YOLO-seg | YOLOv8-seg n/s/m/l/x |
| **Semantic Segmentation** | MMSegmentation | SegFormer-B0/B2/B5, DeepLabV3+ |

---

## Python SDK

```bash
pip install ./sdks/python-sdk
```

```python
from visionforge import VisionForgeClient

client = VisionForgeClient("http://localhost:8000")
client.login("user@example.com", "password")

# Upload images
project = client.get_project("my-project-id")
client.upload_folder(project, "./my_images/")

# Run inference
result = client.predict(endpoint_id="abc123", image_path="photo.jpg")
print(result["predictions"])

# Load a local ONNX model
from visionforge import VisionModel
model = VisionModel.from_onnx("model.onnx", label_map={0: "cat", 1: "dog"})
detections = model.predict("photo.jpg")
```

---

## JavaScript / TypeScript SDK

```bash
npm install ./sdks/js-sdk
```

```typescript
import { VisionForgeClient } from '@visionforge/sdk'

const client = new VisionForgeClient({ baseUrl: 'http://localhost:8000' })
await client.login('user@example.com', 'password')

// Single image inference
const result = await client.predict('endpoint-id', imageFile)

// Real-time video stream
const session = client.createStreamSession('endpoint-id', {
  onPrediction: (data) => console.log(data.predictions),
  confidenceThreshold: 0.4,
})
session.sendFrame(canvas)
session.close()
```

---

## No-Code Workflow Builder

Build real-time vision pipelines by connecting nodes in the browser at **Workflows → New Workflow**.

**Example: Count vehicles crossing a line**
```
RTSPStream → DetectObjects → TrackObjects → CountObjects → LiveDashboard
                                                         → SaveToDB
                                                         → TriggerAlert
```

**Available node types:**

| Category | Nodes |
|---|---|
| Input | CameraCapture, RTSPStream, VideoFile |
| Vision | DetectObjects, ClassifyImage, TrackObjects, CountObjects, ExtractROI, DrawAnnotations |
| Logic | FilterByClass, FilterByConfidence, Conditional, Throttle, Aggregate |
| Output | LiveDashboard, SaveToDB, TriggerAlert, ExportCSV, RobotOutput |

---

## Export Formats

Trained models can be exported from the Model Registry:

| Format | Use case |
|---|---|
| **ONNX** | Cross-platform production inference (used by infer_api) |
| **TFLite** | Mobile / embedded devices |
| **CoreML** | Apple devices (iOS, macOS) |
| **OpenVINO** | Intel CPU/VPU acceleration |
| **TorchScript** | PyTorch serving |
| **NCNN** | Mobile (Android, ARM) |
| **TensorRT** | NVIDIA GPU (maximum throughput) |

Dataset exports (for use outside the platform):

**COCO JSON**, **YOLO TXT**, **Pascal VOC XML**, **TFRecord**, **CreateML JSON**, **CSV**

---

## Configuration

All configuration is via environment variables in `.env`. Key settings:

| Variable | Default | Description |
|---|---|---|
| `JWT_SECRET` | *(change this)* | Secret key for signing auth tokens |
| `DATABASE_URL` | local postgres | PostgreSQL connection string |
| `REDIS_URL` | local redis | Redis connection string |
| `MINIO_URL` | local minio | Object storage endpoint |
| `MLFLOW_TRACKING_URI` | local mlflow | Experiment tracking server |
| `SAM2_MODEL` | `sam2_hiera_large` | SAM2 checkpoint to use |
| `CLIP_MODEL` | `openai/clip-vit-base-patch32` | CLIP model for auto-classification |

---

## Troubleshooting

**Services won't start**
```bash
# Check which containers failed
docker compose -f infra/docker-compose.yml ps
docker compose -f infra/docker-compose.yml logs <service-name>
```

**Port already in use**
Change the host-side port in `infra/docker-compose.yml` (left side of `host:container`).

**Database migration fails**
Ensure the `postgres` service is healthy before running migrations:
```bash
docker compose -f infra/docker-compose.yml ps postgres
```

**GPU not detected inside containers (Windows)**
- Ensure WSL 2 backend is selected in Docker Desktop → Settings → General
- Install the latest NVIDIA Game Ready or Studio driver (≥ 527.41)
- Verify with: `docker run --rm --gpus all nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi`

**MinIO buckets missing**
The `core_api` service creates the `visionforge-media` bucket automatically on startup. If it fails, open the MinIO console at http://localhost:9001 and create it manually.

**Slow performance on Windows**
Place the repository inside the WSL 2 filesystem (`\\wsl$\Ubuntu\home\<user>\`) rather than the Windows filesystem (`C:\`) for significantly faster Docker volume performance.
