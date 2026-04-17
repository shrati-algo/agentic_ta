.PHONY: up down migrate seed serve test test-unit test-integration eval lint format build \
        dev-ui install-ui test-ui build-ui

up:
	docker compose up -d

down:
	docker compose down

migrate:
	alembic upgrade head

seed:
	python scripts/seed_db.py

serve:
	uvicorn tad.main:app --reload --host 0.0.0.0 --port 8000

test: lint
	pytest

test-unit:
	pytest tests/unit

test-integration:
	pytest tests/integration

eval:
	python -m tad.evals.eval

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/
	mypy src/tad/

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

build:
	docker build -t tad:$$(git rev-parse --short HEAD) .

# ---- Frontend ------------------------------------------------------------

install-ui:
	cd frontend && npm install

dev-ui:
	cd frontend && npm run dev

test-ui:
	cd frontend && npm test

build-ui:
	cd frontend && npm run build
