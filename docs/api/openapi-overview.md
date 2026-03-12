# VisionForge API Overview

VisionForge exposes four FastAPI services, each with auto-generated OpenAPI documentation.

## Service URLs (local development)

| Service | URL | Docs |
|---------|-----|------|
| Core API | http://localhost:8000 | http://localhost:8000/docs |
| Training API | http://localhost:8001 | http://localhost:8001/docs |
| Inference API | http://localhost:8002 | http://localhost:8002/docs |
| AI Assist | http://localhost:8003 | http://localhost:8003/docs |

Via Nginx reverse proxy (port 80):

| Path | Backend |
|------|---------|
| `/api/core/` | Core API |
| `/api/train/` | Training API |
| `/api/infer/` | Inference API |
| `/api/ai/` | AI Assist |
| `/ws/` | WebSocket (training + workflow) |

## Authentication

All endpoints (except `/auth/register` and `/auth/login`) require a Bearer token:

```
Authorization: Bearer <access_token>
```

Access tokens expire after 15 minutes. Use the refresh token (stored in httponly cookie) to get a new one:

```http
POST /api/core/auth/refresh
```

## Key Endpoints

### Data Management (Core API)

```
POST   /api/core/projects              Create project
GET    /api/core/projects?org_id=...   List projects
POST   /api/core/datasets              Create dataset
POST   /api/core/images/{did}/upload   Upload images
GET    /api/core/images/{did}/images   List images (paginated)
PUT    /api/core/annotations/images/{iid}/annotations  Save annotations
POST   /api/core/datasets/{did}/versions  Create dataset version
POST   /api/core/exports/{vid}         Export dataset version
```

### Training (Train API)

```
POST   /api/train/training-jobs           Launch training job
GET    /api/train/training-jobs/{id}      Get job status
GET    /api/train/training-jobs/{id}/metrics  Epoch metrics
WS     ws://localhost:8001/ws/training/{id}   Live training progress
POST   /api/train/model-versions/{id}/promote  Promote model stage
POST   /api/train/model-versions/{id}/export   Export to ONNX/TFLite/etc
```

### Inference (Inference API)

```
POST   /api/infer/predict/{endpoint_id}         Single image inference
POST   /api/infer/predict/{endpoint_id}/base64  Base64 image inference
WS     ws://localhost:8002/ws/stream/{endpoint_id}  Real-time video inference
POST   /api/infer/endpoints                     Create endpoint
PATCH  /api/infer/endpoints/{id}               Update endpoint
```

### AI Assist

```
POST   /api/ai/sam/segment    SAM2 segmentation with point/box prompts
POST   /api/ai/clip/suggest   CLIP-based classification suggestions
```

## WebSocket Protocol

### Training Progress (`/ws/training/{job_id}`)

Server sends:
```json
{"type": "epoch", "epoch": 42, "total_epochs": 100, "metrics": {"train_loss": 0.32, "mAP50": 0.76}}
{"type": "status", "status": "completed", "best_metric": 0.823}
```

### Inference Stream (`/ws/stream/{endpoint_id}`)

Client sends:
```json
{"frame": "<base64 JPEG>", "confidence_threshold": 0.25}
```

Server sends:
```json
{"type": "prediction", "frame_number": 42, "predictions": [...], "inference_ms": 18.3}
```
