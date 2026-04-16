# ---------- Stage 1: Frontend build (placeholder for Phase 12+) ----------
FROM node:20-alpine AS frontend
WORKDIR /build
# When the frontend exists, uncomment:
# COPY frontend/package.json frontend/package-lock.json ./
# RUN npm ci
# COPY frontend/ .
# RUN npm run build
RUN mkdir -p /build/dist

# ---------- Stage 2: Backend ----------
FROM python:3.11-slim AS backend

RUN groupadd --gid 1000 tad \
    && useradd --uid 1000 --gid tad --create-home tad

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY src/ src/
COPY configs/ configs/
COPY --from=frontend /build/dist /app/dist

RUN chown -R tad:tad /app
USER tad

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=2s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/v1/health')"]

CMD ["uvicorn", "tad.main:app", "--host", "0.0.0.0", "--port", "8000"]
