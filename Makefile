.PHONY: help install test lint format migrate dev-api docker-up docker-down tf-validate

PYTHON ?= python
PIP ?= pip
TERRAFORM ?= terraform

help:
	@echo "Available commands:"
	@echo "  make install      Install production and development dependencies"
	@echo "  make test         Execute Pytest test suite"
	@echo "  make lint         Run Ruff linter"
	@echo "  make format       Format code with Ruff"
	@echo "  make migrate      Run Alembic database migrations"
	@echo "  make dev-api      Start FastAPI local server"
	@echo "  make docker-up    Start PostgreSQL and Auth API in Docker Compose"
	@echo "  make docker-down  Stop Docker Compose stack"
	@echo "  make tf-validate  Validate all Terraform environments"

install:
	$(PIP) install -r requirements.txt -r requirements-dev.txt

test:
	$(PYTHON) -m pytest -v

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff format .

migrate:
	$(PYTHON) -m alembic upgrade head

dev-api:
	$(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down -v

tf-validate:
	@echo "Validating Terraform Dev..."
	$(TERRAFORM) -chdir=terraform/environments/dev validate
	@echo "Validating Terraform QA..."
	$(TERRAFORM) -chdir=terraform/environments/qa validate
	@echo "Validating Terraform Prod..."
	$(TERRAFORM) -chdir=terraform/environments/prod validate
