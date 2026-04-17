.PHONY: up down migrate seed serve demo demo-seed test test-unit test-integration eval lint format build \
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

# Run the backend in demo mode: in-memory storage, no Docker required.
# Use this when you just want to boot the UI end-to-end locally.
demo:
	python scripts/run_demo.py

# Drop a handful of matched chassis image pairs into the watched folders
# while `make demo` is running -- watch the dashboard fill up live.
# Usage: `make demo-seed` (defaults to 5 pairs) or `python scripts/seed_demo.py 20`.
demo-seed:
	python scripts/seed_demo.py

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
