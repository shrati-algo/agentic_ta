# ---------- Stage 1: frontend build ----------
FROM node:20-alpine AS frontend

WORKDIR /build

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: backend runtime ----------
FROM python:3.11-slim AS backend

# opencv-python needs libGL + libglib; curl is for the healthcheck
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 tad \
    && useradd --uid 1000 --gid tad --create-home tad

WORKDIR /app

# Install Python deps first so they cache independently of source changes
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Application code + config
COPY src/ src/
COPY configs/ configs/
COPY scripts/ scripts/
# alembic.ini so migrations can be run from the container:
#     docker compose exec tad alembic upgrade head
COPY alembic.ini ./

# run_demo.py wires the in-memory repository fakes that live under tests/
# (tests/fakes.py + tests/__init__.py). The bulky tests/fixtures/test_images
# directory is NOT baked in -- it is bind-mounted at runtime from compose.
COPY tests/__init__.py tests/__init__.py
COPY tests/fakes.py tests/fakes.py
COPY tests/fixtures/images/ tests/fixtures/images/

# Pre-built UI from stage 1. The SPA fallback in src/tad/api/app.py looks
# for frontend/dist relative to the repo root, i.e. /app/frontend/dist.
COPY --from=frontend /build/dist /app/frontend/dist

RUN chown -R tad:tad /app
USER tad

# `pip install .` above only resolved the dependency wheels -- make the
# 'tad' package itself importable without re-running hatchling on every
# rebuild. scripts/run_demo.py already inserts this path at runtime;
# setting it here also lets `alembic` (and any one-off `python -m tad.*`
# invocation) work inside the container.
ENV PYTHONPATH=/app/src

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/v1/health || exit 1

# Demo-mode entrypoint: in-memory repos + blob store, single port, no
# external services required. To run the production entrypoint instead
# (real Postgres + MinIO), override CMD:
#     docker run ... tad uvicorn tad.main:app --host 0.0.0.0 --port 8000
CMD ["python", "scripts/run_demo.py"]
