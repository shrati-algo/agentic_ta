.PHONY: setup up down migrate seed serve run demo demo-seed test test-unit test-integration eval bench lint format build clean \
        dev-ui install-ui test-ui build-ui

setup:
	pip install -e ".[dev]"

run: serve

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

bench: ## Run benchmark suite and write report
	@mkdir -p reports/benchmark
	@ts=$$(date -u +%Y%m%dT%H%M%SZ); \
	  pytest tests/benchmark -v --tb=short \
	  | tee reports/benchmark/run-$${ts}.log
	@echo "Report log -> reports/benchmark/run-*.log"
	@echo "Fill TEMPLATE.md and save as reports/benchmark/<run-id>.md"

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage coverage.xml htmlcov
	find . -name __pycache__ -type d -not -path './.git/*' -not -path './_archive/*' -exec rm -rf {} + 2>/dev/null || true
	find . -name '*.egg-info' -type d -not -path './.git/*' -not -path './_archive/*' -exec rm -rf {} + 2>/dev/null || true

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/
	mypy src/tad/

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

build:
	docker build -t tad:latest -t tad:$$(git rev-parse --short HEAD) .

# ---- Frontend ------------------------------------------------------------

install-ui:
	cd frontend && npm install

dev-ui:
	cd frontend && npm run dev

test-ui:
	cd frontend && npm test

build-ui:
	cd frontend && npm run build
