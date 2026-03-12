# VisionForge Platform — Makefile
# Run `make help` to see available commands

.PHONY: help up down up-gpu logs migrate seed lint test build clean

COMPOSE = docker compose -f infra/docker-compose.yml
COMPOSE_GPU = docker compose -f infra/docker-compose.yml -f infra/docker-compose.gpu.yml

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Development ───────────────────────────────────────────────────────────────

up: ## Start all services (CPU only)
	$(COMPOSE) up -d
	@echo "Services started. Access the platform at http://localhost"

up-gpu: ## Start all services with GPU support
	$(COMPOSE_GPU) --profile gpu up -d

down: ## Stop all services
	$(COMPOSE) down

restart: ## Restart all services
	$(COMPOSE) restart

logs: ## Follow all service logs
	$(COMPOSE) logs -f

logs-api: ## Follow core API logs
	$(COMPOSE) logs -f core_api

logs-train: ## Follow training API logs
	$(COMPOSE) logs -f train_api

logs-worker: ## Follow Celery worker logs
	$(COMPOSE) logs -f celery_worker

shell-api: ## Open shell in core API container
	$(COMPOSE) exec core_api bash

shell-db: ## Open PostgreSQL shell
	$(COMPOSE) exec postgres psql -U visionforge visionforge

# ── Database ──────────────────────────────────────────────────────────────────

migrate: ## Run Alembic database migrations
	$(COMPOSE) exec core_api alembic upgrade head

migrate-create: ## Create a new migration (MSG=description)
	$(COMPOSE) exec core_api alembic revision --autogenerate -m "$(MSG)"

migrate-downgrade: ## Downgrade one migration
	$(COMPOSE) exec core_api alembic downgrade -1

seed: ## Seed database with sample data
	$(COMPOSE) exec core_api python scripts/seed.py

# ── Development (local, no Docker) ───────────────────────────────────────────

dev-api: ## Run core API locally (requires local Postgres+Redis+MinIO)
	cd backend && uvicorn core_api.main:app --host 0.0.0.0 --port 8000 --reload

dev-train: ## Run train API locally
	cd backend && uvicorn train_api.main:app --host 0.0.0.0 --port 8001 --reload

dev-infer: ## Run inference API locally
	cd backend && uvicorn infer_api.main:app --host 0.0.0.0 --port 8002 --reload

dev-worker: ## Run Celery worker locally
	cd backend && celery -A train_api.workers.celery_app worker --loglevel=info -Q default,export

dev-frontend: ## Run frontend dev server
	cd frontend && npm run dev

# ── Testing ───────────────────────────────────────────────────────────────────

test: ## Run all tests
	cd backend && pytest tests/ -v --cov=. --cov-report=term-missing

test-unit: ## Run unit tests only
	cd backend && pytest tests/unit/ -v

test-integration: ## Run integration tests (requires running services)
	cd backend && pytest tests/integration/ -v

test-e2e: ## Run end-to-end tests
	cd frontend && npm run test

# ── Linting & Formatting ──────────────────────────────────────────────────────

lint: ## Run all linters
	cd backend && ruff check .
	cd frontend && npm run lint

lint-fix: ## Auto-fix linting issues
	cd backend && ruff check . --fix
	cd frontend && npm run lint -- --fix

type-check: ## Run type checking
	cd backend && mypy backend/
	cd frontend && npm run type-check

format: ## Format code
	cd backend && ruff format .

# ── Build ─────────────────────────────────────────────────────────────────────

build: ## Build all Docker images
	$(COMPOSE) build

build-frontend: ## Build frontend production bundle
	cd frontend && npm run build

build-sdk: ## Build Python SDK
	cd sdks/python-sdk && python setup.py bdist_wheel

# ── Cleanup ───────────────────────────────────────────────────────────────────

clean: ## Remove stopped containers and volumes
	$(COMPOSE) down -v --remove-orphans

clean-models: ## Remove cached ML model files
	rm -rf ~/.cache/sam2 ~/.cache/torch ~/.cache/huggingface

clean-temp: ## Remove training temp files
	rm -rf /tmp/visionforge

# ── Monitoring ────────────────────────────────────────────────────────────────

open-grafana: ## Open Grafana in browser
	@open http://localhost:3001 || xdg-open http://localhost:3001

open-mlflow: ## Open MLflow in browser
	@open http://localhost:5000 || xdg-open http://localhost:5000

open-minio: ## Open MinIO console in browser
	@open http://localhost:9001 || xdg-open http://localhost:9001

open-prometheus: ## Open Prometheus in browser
	@open http://localhost:9090 || xdg-open http://localhost:9090
