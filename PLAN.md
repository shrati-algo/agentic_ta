# Trailing Arm Detection -- Implementation Plan

> **Status**: Draft | **Created**: 2026-04-16 | **Greenfield**: yes (no `src/` exists yet)
>
> This plan covers the end-to-end build from an empty repo to a production-ready
> service + frontend. Each phase is independently shippable and testable.
> Do not skip phases -- each one builds on the last.

---

## Phase 0 -- Project Scaffold & Dev Environment

**Goal**: A repo that builds, lints, tests (empty), and serves a health endpoint.

### Deliverables
- Git repo initialised with `.gitignore`, `.env.example`
- `pyproject.toml` with all pinned backend dependencies (see CLAUDE.md tech stack)
- `Makefile` with all targets listed in CLAUDE.md (up, down, migrate, serve, test, lint, format, build, etc.)
- `docker-compose.yml` for local Postgres + MinIO
- `Dockerfile` (multi-stage: Node 20 for frontend build + Python 3.11 for backend)
- `.pre-commit-config.yaml` with ruff + mypy hooks
- `ruff.toml` / `pyproject.toml` ruff section (line-length 100, import order)
- Minimal FastAPI app at `src/tad/main.py` with `/v1/health` returning `200`
- `src/tad/__init__.py`
- `.github/workflows/ci-backend.yml` (ruff + mypy + pytest placeholder)
- ADR directory: `docs/decisions/ADR-001.md` (classical CV only)
- `CLAUDE.md` committed (already exists, may need path adjustments for `backend/` vs flat layout)

### Files to Create
```
pyproject.toml
Makefile
Dockerfile
docker-compose.yml
.gitignore
.env.example
.pre-commit-config.yaml
src/tad/__init__.py
src/tad/main.py
docs/decisions/ADR-001.md
.github/workflows/ci-backend.yml
```

### Test Gate
- [ ] `make lint` passes (ruff + mypy on empty `src/tad/`)
- [ ] `make test` passes (pytest discovers zero tests, exits 0)
- [ ] `make up` starts Postgres + MinIO containers
- [ ] `curl http://localhost:8000/v1/health` returns `200`
- [ ] CI workflow is green on push

---

## Phase 1 -- Configuration Layer

**Goal**: Settings, AlgoParams, and Calibration models load, validate, and are tested.

### Deliverables
- `src/tad/config/__init__.py`
- `src/tad/config/settings.py` -- Pydantic Settings reading `.env`
- `src/tad/config/algo_params.py` -- `AlgoParams` Pydantic model + `load_algo_params(version)` loader
- `src/tad/config/calibration.py` -- `Calibration` Pydantic model + `load_calibration(path)` loader
- `configs/algo_params/algo-1.2.0.yaml` -- initial algo params (from TRD Section 11)
- `configs/calibration/cal-2026-03-14-L.yaml` -- left camera calibration
- `configs/calibration/cal-2026-03-14-R.yaml` -- right camera calibration
- `/v1/ready` endpoint -- returns 200 only when both calibrations load and both image dirs exist

### Files to Create
```
src/tad/config/__init__.py
src/tad/config/settings.py
src/tad/config/algo_params.py
src/tad/config/calibration.py
configs/algo_params/algo-1.2.0.yaml
configs/calibration/cal-2026-03-14-L.yaml
configs/calibration/cal-2026-03-14-R.yaml
tests/unit/test_settings.py
tests/unit/test_algo_params.py
tests/unit/test_calibration.py
```

### Test Gate
- [ ] Unit tests cover: valid load, missing file, bad YAML, camera-side mismatch
- [ ] `make test-unit` green
- [ ] `/v1/ready` returns 503 when calibration is missing, 200 when present

---

## Phase 2 -- Data Layer (Filename Parser + Image Validator + Safe Read)

**Goal**: Pure functions that parse filenames and validate images, fully tested.

### Deliverables
- `src/tad/data/__init__.py`
- `src/tad/data/filename_parser.py` -- `FILENAME_RE`, `ParsedName`, `parse_filename()`
- `src/tad/data/image_validator.py` -- `validate_image()` with all gates (resolution, blur, exposure, integrity)
- `src/tad/data/safe_read.py` -- `wait_for_stable()` async size-stability loop
- `src/tad/api/errors.py` -- domain exceptions: `BadFilename`, `ImageQualityError`, etc.
- Test fixture images under `tests/fixtures/images/` (valid L/R pair, plus deliberately bad images)
- Test fixture calibration YAMLs under `tests/fixtures/calibration/`

### Files to Create
```
src/tad/data/__init__.py
src/tad/data/filename_parser.py
src/tad/data/image_validator.py
src/tad/data/safe_read.py
src/tad/api/__init__.py
src/tad/api/errors.py
tests/unit/test_filename_parser.py
tests/unit/test_image_validator.py
tests/unit/test_safe_read.py
tests/fixtures/images/MALBB51BLPM123456_L.jpg
tests/fixtures/images/MALBB51BLPM123456_R.jpg
tests/fixtures/images/bad_name.jpg
tests/fixtures/images/truncated.jpg
tests/fixtures/images/blurry.jpg
tests/fixtures/calibration/cal-test-L.yaml
tests/fixtures/calibration/cal-test-R.yaml
```

### Test Gate
- [ ] 100% branch coverage on `filename_parser.py` and `image_validator.py`
- [ ] Valid filenames parse correctly; invalid ones raise `BadFilename`
- [ ] All image quality gates (resolution, blur, exposure, integrity) have positive and negative test cases
- [ ] `make test-unit` green

---

## Phase 3 -- Measurement Pipeline (Offline, Pure CV)

**Goal**: A function that takes an image + calibration + algo_params and returns a diameter in mm. No I/O, no DB, no sessions. This is the heart of the system.

**Approach**: `algo-1.3.0` — see [ADR-008](docs/decisions/ADR-008.md). The pipeline is target-driven: the operator passes a known expected diameter (e.g. 47.25 mm), and the detector only accepts circles whose radius falls in `target_diameter_mm ± radius_tolerance_mm`. This eliminates the phantom-circle problem seen with the original Canny+RANSAC pipeline on real images.

### Deliverables
- `src/tad/measurement/__init__.py`
- `src/tad/measurement/models.py` -- `PipelineInput`, `PipelineOutput`, `InnerCircle` (frozen dataclasses)
- `src/tad/measurement/preprocessing.py` -- `gaussian_blur()`
- `src/tad/measurement/threshold.py` -- `adaptive_threshold()`, `morph_close()`
- `src/tad/measurement/contour_detect.py` -- `find_candidate_contours()`, `detect_circle_in_contour()`, `detect_circle()`
- `src/tad/measurement/confidence.py` -- `compute_confidence()`, `evaluate_status()` (band-based)
- `src/tad/measurement/annotate.py` -- `render_debug_image()` with target reference circle
- `src/tad/measurement/pipeline.py` -- `measure_innermost_diameter()` orchestrator
- `src/tad/measurement/__main__.py` -- CLI entry point
- `configs/algo_params/algo-1.3.0.yaml` -- new parameter schema

### Files to Create
```
src/tad/measurement/__init__.py
src/tad/measurement/models.py
src/tad/measurement/preprocessing.py
src/tad/measurement/threshold.py
src/tad/measurement/contour_detect.py
src/tad/measurement/confidence.py
src/tad/measurement/annotate.py
src/tad/measurement/pipeline.py
src/tad/measurement/__main__.py
configs/algo_params/algo-1.3.0.yaml
tests/unit/test_preprocessing.py
tests/unit/test_threshold.py
tests/unit/test_contour_detect.py
tests/unit/test_confidence.py
tests/unit/test_pipeline.py
```

### Test Gate
- [ ] On fixture images, measured diameter matches target within `somewhat_ok_band_mm`
- [ ] Determinism: same image + params -> identical output (no stochastic sampling)
- [ ] `detect_circle` walks contours largest-first and rejects circles outside the target radius band
- [ ] `ERR_NO_CIRCLE` returned when no contour yields a matching circle
- [ ] Band classification covers every leg of the status matrix (PASS / REVIEW / FAIL / ERROR)
- [ ] `make test-unit` green
- [ ] Pipeline CLI runs end-to-end on a fixture image and emits a debug JPG

---

## Phase 4 -- Persistence Layer (Postgres + MinIO)

**Goal**: Rows in Postgres, blobs in MinIO, round-trip tested.

### Deliverables
- `src/tad/persistence/__init__.py`
- `src/tad/persistence/db.py` -- async SQLAlchemy engine factory, session maker
- `src/tad/persistence/models.py` -- SQLAlchemy mapped classes (sessions, measurements, chassis_records, calibrations)
- `src/tad/persistence/repositories.py` -- `SessionRepository`, `MeasurementRepository`, `ChassisRepository`
- `src/tad/persistence/blob_store.py` -- `DebugImageStore` (MinIO put/stream)
- `src/tad/persistence/migrations/` -- Alembic setup
- `src/tad/persistence/migrations/versions/001_initial_schema.py` -- all 4 tables (DDL from architecture.txt Section 7)

### Files to Create
```
src/tad/persistence/__init__.py
src/tad/persistence/db.py
src/tad/persistence/models.py
src/tad/persistence/repositories.py
src/tad/persistence/blob_store.py
src/tad/persistence/migrations/env.py
src/tad/persistence/migrations/script.py.mako
src/tad/persistence/migrations/versions/001_initial_schema.py
alembic.ini
tests/integration/__init__.py
tests/integration/test_repositories.py
tests/integration/test_blob_store.py
scripts/seed_db.py
```

### Test Gate
- [ ] `make up && make migrate` creates all 4 tables in Postgres
- [ ] Integration test: insert and read a Session, Measurement, ChassisRecord round-trip
- [ ] Integration test: put and stream a debug image through MinIO round-trip
- [ ] All IDs are client-side UUIDs, all timestamps are TIMESTAMPTZ in UTC
- [ ] `make test-integration` green (requires `make up`)

---

## Phase 5 -- Chassis Aggregator

**Goal**: Given two per-camera measurements, produce a chassis record with the correct overall status.

### Deliverables
- `src/tad/sessions/__init__.py`
- `src/tad/sessions/aggregator.py` -- `Aggregator` class with `accept()` and `flush()`
- Status matrix implementation (TRD Section 7.1)
- Asymmetry threshold downgrade logic

### Files to Create
```
src/tad/sessions/__init__.py
src/tad/sessions/aggregator.py
tests/unit/test_aggregator.py
```

### Test Gate
- [ ] Every cell of the 4x4 status matrix is covered by a unit test
- [ ] Asymmetry threshold downgrade: PASS -> REVIEW when asymmetry > threshold
- [ ] `flush()` emits REVIEW with "missing side: L" or "missing side: R" for orphans
- [ ] Concurrency: aggregator handles rapid `accept()` calls safely
- [ ] `make test-unit` green

---

## Phase 6 -- SSE Event Broker

**Goal**: Per-session fan-out of events to connected dashboards, with slow-subscriber protection.

### Deliverables
- `src/tad/sessions/broker.py` -- `SseBroker` class (subscribe/unsubscribe/publish)
- `src/tad/api/sse.py` -- SSE streaming route helper
- Event types: `session_opened`, `camera_result`, `chassis_result`, `warning`, `session_closed`

### Files to Create
```
src/tad/sessions/broker.py
src/tad/api/sse.py
tests/unit/test_broker.py
tests/integration/test_api_sse.py
```

### Test Gate
- [ ] Two concurrent subscribers both receive the same published event
- [ ] A slow subscriber (full queue) is dropped, not blocking the producer
- [ ] Unsubscribe cleans up correctly
- [ ] SSE route streams events in the correct `event: <type>\ndata: <json>` format
- [ ] `make test-unit` and `make test-integration` green

---

## Phase 7 -- Folder Watchers + Consumer Loop

**Goal**: Dropping a file into `/tmp/tad/images/left/` triggers the full pipeline (validate -> parse -> measure -> persist -> publish -> aggregate).

### Deliverables
- `src/tad/sessions/watcher.py` -- `FolderWatcher` using watchdog + `loop.call_soon_threadsafe`
- `src/tad/sessions/consumer.py` -- `process_item()` loop (safe-read -> validate -> parse -> measure via `asyncio.to_thread` -> upload debug image -> insert measurement -> publish camera_result -> aggregator.accept)
- `src/tad/sessions/runtime.py` -- `SessionRuntime` dataclass (holds queue, watchers, aggregator, broker, algo_params, calibrations)

### Files to Create
```
src/tad/sessions/watcher.py
src/tad/sessions/consumer.py
src/tad/sessions/runtime.py
tests/integration/test_watcher.py
tests/integration/test_consumer.py
```

### Test Gate
- [ ] Integration test: drop a fixture image into a temp directory -> watcher enqueues it -> consumer processes it -> measurement row exists in DB -> SSE event was published
- [ ] Safe-read protocol handles partially written files (size changes between checks)
- [ ] Bad filenames produce `warning` events, not crashes
- [ ] Already-seen files (same path + mtime) are deduplicated
- [ ] `make test-integration` green

---

## Phase 8 -- Session Manager + API Routes

**Goal**: Full session lifecycle (start -> process images -> stop) behind HTTP endpoints.

### Deliverables
- `src/tad/sessions/manager.py` -- `SessionManager` class (start, stop, require_active)
- `src/tad/api/app.py` -- FastAPI application factory with lifespan, middleware, exception handlers
- `src/tad/api/deps.py` -- FastAPI `Depends()` wiring for session manager, repos, etc.
- `src/tad/api/schemas.py` -- all Pydantic request/response models (StartRequest, StartResponse, StopResponse, CameraResultEvent, ChassisResultEvent, ErrorEnvelope, etc.)
- `src/tad/api/routes_sessions.py` -- `POST /v1/sessions/start`, `POST /v1/sessions/{id}/stop`, `GET /v1/sessions/{id}/events` (SSE), `GET /v1/sessions/{id}/results` (polling fallback)
- `src/tad/api/routes_measurements.py` -- `GET /v1/measurements/{id}`, `GET /v1/debug/{id}`
- `src/tad/api/routes_health.py` -- `GET /v1/health`, `GET /v1/ready`
- `src/tad/api/routes_chassis.py` -- `GET /v1/chassis`, `GET /v1/chassis/{id}`, `POST /v1/chassis/{id}/decision`, `POST /v1/chassis/{id}/flag`
- `src/tad/api/routes_dashboard.py` -- `GET /v1/dashboard/summary`
- Request ID middleware (generates `X-Request-Id`, binds to structlog)
- Error envelope handler mapping domain exceptions to `ERR_*` codes

### Files to Create
```
src/tad/sessions/manager.py
src/tad/api/app.py
src/tad/api/deps.py
src/tad/api/schemas.py
src/tad/api/routes_sessions.py
src/tad/api/routes_measurements.py
src/tad/api/routes_health.py
src/tad/api/routes_chassis.py
src/tad/api/routes_dashboard.py
src/tad/api/middleware.py
tests/integration/test_session_flow.py
tests/integration/test_api_routes.py
```

### Test Gate
- [ ] End-to-end curl walkthrough works: start session -> drop fixture images -> events stream -> stop session with summary
- [ ] `POST /start` returns 201 with full session metadata
- [ ] `POST /start` when already active returns error (no duplicate sessions)
- [ ] `POST /stop` flushes orphans and returns summary
- [ ] `GET /chassis` returns paginated chassis records with filters (status, shift, date range, search)
- [ ] `GET /chassis/{id}` returns both per-camera measurements
- [ ] `POST /chassis/{id}/decision` records operator decision
- [ ] `POST /chassis/{id}/flag` toggles flagged state
- [ ] `GET /dashboard/summary` returns KPI cards, trend, and recent alerts
- [ ] `GET /debug/{id}` streams the annotated JPEG
- [ ] Error envelope: no stack traces reach the client; all errors have `error_code` + `request_id`
- [ ] `make test-integration` green
- [ ] `make serve` works with `--reload`

---

## Phase 9 -- Observability

**Goal**: Production-readiness hygiene -- structured logging, metrics, request tracing.

### Deliverables
- `src/tad/observability/__init__.py`
- `src/tad/observability/logging_conf.py` -- structlog configuration (JSON output, context binding for session_id, measurement_id, chassis_no, camera_side)
- `src/tad/observability/metrics.py` -- Prometheus collectors:
  - `images_processed_total{side, status}`
  - `chassis_results_total{status}`
  - `warnings_total{reason}`
  - `image_latency_seconds{side}`
  - `confidence_score{side}`
  - `diameter_mm{side}`
  - `asymmetry_mm`
  - `sessions_active`
  - `pending_chassis_count{session_id}`
- `/metrics` endpoint for Prometheus scraping
- Chassis number hashing for info/warn logs (plaintext only in debug)

### Files to Create
```
src/tad/observability/__init__.py
src/tad/observability/logging_conf.py
src/tad/observability/metrics.py
tests/unit/test_logging_conf.py
tests/unit/test_metrics.py
```

### Test Gate
- [ ] All log records carry `session_id`, `measurement_id`, `chassis_no` (hashed at info level), `camera_side`
- [ ] `/metrics` returns Prometheus-format text with all declared collectors
- [ ] `X-Request-Id` is generated, logged, and returned in response headers
- [ ] `make test-unit` green

---

## Phase 10 -- Eval Harness

**Goal**: A locked evaluation set with a pass/fail gate for any change to the measurement pipeline or algo_params.

### Deliverables
- `src/tad/evals/__init__.py`
- `src/tad/evals/eval.py` -- eval runner that loads the dataset, runs pipeline, computes MAE / P95 / max error
- `src/tad/evals/metrics.py` -- metric computation helpers
- `tests/eval/dataset.csv` -- locked eval set (chassis_no, image_path, side, caliper_mm)
- `scripts/validate_algo_params.py` -- promotion script that enforces eval gate + ADR check
- `.github/workflows/eval.yml` -- runs on every PR touching `src/tad/measurement/` or `configs/algo_params/`

### Files to Create
```
src/tad/evals/__init__.py
src/tad/evals/eval.py
src/tad/evals/metrics.py
tests/eval/dataset.csv
scripts/validate_algo_params.py
.github/workflows/eval.yml
```

### Test Gate
- [ ] `make eval` runs end-to-end and produces a report with MAE, P95, max error
- [ ] Current pipeline meets accuracy targets: MAE <= 0.05 mm, P95 <= 0.10 mm, max <= 0.20 mm
- [ ] A deliberate regression (bad algo_params) fails the eval gate
- [ ] Eval workflow triggers on PRs touching measurement code
- [ ] `make eval` is green

---

## Phase 11 -- Backend Hardening & Release Prep

**Goal**: The backend is production-ready -- graceful shutdown, error hardening, Docker finalization.

### Deliverables
- Graceful shutdown via Uvicorn lifespan events (SIGTERM -> stop all active sessions with drain budget)
- Idempotency guard: `(session_id, absolute_path, file_mtime)` dedup in consumer
- Error envelope standardisation (consistent `ERR_*` codes across all routes)
- Dockerfile finalised: non-root user, healthcheck instruction, multi-stage (Node 20 + Python 3.11)
- `scripts/replay_session.py` -- replay a set of images through the service for staging validation
- `scripts/run_calibration.py` -- calibration script stub
- `.github/workflows/cd.yml` -- on tag push, builds and pushes Docker image

### Files to Create
```
scripts/replay_session.py
scripts/run_calibration.py
.github/workflows/cd.yml
```

### Test Gate
- [ ] SIGTERM during an active session: in-flight items complete, orphans are flushed, SSE stream closes cleanly
- [ ] Duplicate image (same path + mtime) produces a debug log, not a second measurement
- [ ] Docker image builds and starts with `make build`
- [ ] `docker compose up` (full stack) runs the service end-to-end
- [ ] Replay script processes a set of fixture images and produces expected results

---

## Phase 12 -- Frontend Scaffold

**Goal**: A React SPA that builds, routes between two pages, and renders a shared header.

### Deliverables
- `frontend/package.json` with all pinned frontend dependencies (React 18.3, Vite 5.4, Tailwind 3.4, Recharts 2.12, React Router DOM 6.26, @tanstack/react-table 8.20, Axios 1.7, lucide-react 0.441, @headlessui/react 2.1, date-fns 3.6, TypeScript 5.5)
- `frontend/vite.config.ts` with API proxy to `:8000`
- `frontend/tailwind.config.ts`, `frontend/postcss.config.cjs`
- `frontend/tsconfig.json`
- `frontend/index.html`
- `frontend/src/main.tsx` -- ReactDOM.createRoot
- `frontend/src/App.tsx` -- BrowserRouter + routes
- `frontend/src/routes.ts` -- route constants
- `frontend/src/labels.ts` -- status/camera terminology mapping (single source of truth)
- `frontend/src/styles/index.css` -- Tailwind base
- `frontend/src/pages/Dashboard.tsx` -- skeleton
- `frontend/src/pages/ViolationDetail.tsx` -- skeleton
- `frontend/src/components/Header.tsx` -- logo + nav tabs (Home active, Live View disabled, Settings disabled) + user menu
- `frontend/src/components/StatusPill.tsx` -- status label + colour + icon mapping
- Makefile target: `make dev-ui` (Vite dev server on :5173)
- `.github/workflows/ci-frontend.yml` (ESLint + Prettier + Vitest + Vite build)

### Files to Create
```
frontend/package.json
frontend/vite.config.ts
frontend/tailwind.config.ts
frontend/postcss.config.cjs
frontend/tsconfig.json
frontend/index.html
frontend/src/main.tsx
frontend/src/App.tsx
frontend/src/routes.ts
frontend/src/labels.ts
frontend/src/styles/index.css
frontend/src/pages/Dashboard.tsx
frontend/src/pages/ViolationDetail.tsx
frontend/src/components/Header.tsx
frontend/src/components/StatusPill.tsx
frontend/tests/unit/labels.test.ts
.github/workflows/ci-frontend.yml
```

### Test Gate
- [ ] `cd frontend && npm install && npm run dev` starts Vite on :5173
- [ ] `/home` renders the Dashboard skeleton with the header
- [ ] `/home/details/123` renders the ViolationDetail skeleton with the header
- [ ] `/` redirects to `/home`
- [ ] Unknown routes show NotFound
- [ ] `StatusPill` renders correct label + colour for each status (unit test)
- [ ] `labels.ts` maps PASS->Okay, REVIEW->Somewhat Okay, FAIL->Not Okay, ERROR->Error
- [ ] `npm run build` produces a static bundle in `/dist`
- [ ] CI frontend workflow green

---

## Phase 13 -- Frontend API Layer + SSE Hook

**Goal**: API client modules and the SSE subscription hook that powers real-time updates.

### Deliverables
- `frontend/src/api/client.ts` -- Axios instance with base URL
- `frontend/src/api/dashboard.ts` -- `GET /v1/dashboard/summary`, `GET /v1/chassis` (list)
- `frontend/src/api/chassis.ts` -- `GET /v1/chassis/{id}`, `POST decision`, `POST flag`
- `frontend/src/api/sessions.ts` -- start/stop, get active session
- `frontend/src/api/sse.ts` -- EventSource wrapper with reconnect logic
- `frontend/src/hooks/useLiveSession.ts` -- connects to SSE, exposes `lastEvent` and `connected` state
- `frontend/src/hooks/useChassisList.ts` -- fetches and paginates chassis list
- `SessionContext` in App.tsx -- provides live session state to all components

### Files to Create
```
frontend/src/api/client.ts
frontend/src/api/dashboard.ts
frontend/src/api/chassis.ts
frontend/src/api/sessions.ts
frontend/src/api/sse.ts
frontend/src/hooks/useLiveSession.ts
frontend/src/hooks/useChassisList.ts
frontend/tests/unit/api.test.ts
```

### Test Gate
- [ ] API client modules type-check against the documented response shapes
- [ ] SSE hook reconnects with backoff on disconnect
- [ ] SSE hook parses `camera_result`, `chassis_result`, `warning`, `session_closed` events
- [ ] Vitest green

---

## Phase 14 -- Dashboard Page (Full Implementation)

**Goal**: The Dashboard at `/home` is fully functional with KPI cards, trend chart, alerts, and the Production Details table -- all updating live via SSE.

### Deliverables
- `frontend/src/components/KpiDonut.tsx` -- Recharts PieChart (Violations Today)
- `frontend/src/components/KpiTrend.tsx` -- Recharts LineChart (Violation Trend, two lines)
- `frontend/src/components/AlertsList.tsx` -- Recent Alerts (clickable -> detail page)
- `frontend/src/components/FiltersBar.tsx` -- date range (Today/Past 7 Days/Date Range), shift, condition, search, export
- `frontend/src/components/ProductionTable.tsx` -- @tanstack/react-table with sorting + pagination
- `frontend/src/components/Pagination.tsx` -- page size selector + prev/next
- Dashboard page wired:
  - On mount, fetch dashboard summary + chassis list
  - Discover active session -> subscribe SSE
  - On `chassis_result`: prepend row to table, refetch KPI cards
  - On `session_closed`: close EventSource, show static data
- Empty state: "Waiting for the first chassis. Session started at HH:MM..."
- Status columns use StatusPill component
- Table rows clickable -> navigate to `/home/details/:id`

### Files to Create
```
frontend/src/components/KpiDonut.tsx
frontend/src/components/KpiTrend.tsx
frontend/src/components/AlertsList.tsx
frontend/src/components/FiltersBar.tsx
frontend/src/components/ProductionTable.tsx
frontend/src/components/Pagination.tsx
```

### Test Gate
- [ ] Dashboard renders KPI cards with data from `/v1/dashboard/summary`
- [ ] Production Details table populates from `/v1/chassis`
- [ ] Table sorting works (by timestamp, status)
- [ ] Pagination works (page size, prev/next)
- [ ] Filters (status, shift, date range, search) update the table
- [ ] SSE events prepend new rows to the table in real time
- [ ] Clicking a row navigates to `/home/details/:id`
- [ ] Empty state renders correctly when no data
- [ ] Vitest unit tests for KpiDonut, KpiTrend, StatusPill, FilterBar

---

## Phase 15 -- Violation Detail Page (Full Implementation)

**Goal**: The Violation Detail page at `/home/details/:id` shows both camera images, conditions, operator decision buttons, and the detail panel.

### Deliverables
- `frontend/src/components/CameraCard.tsx` -- debug image + condition + Correct/Incorrect buttons
- `frontend/src/components/DetailPanel.tsx` -- KV list (Product ID, Overall Condition, Timestamp, Shift, Area) + Flagged toggle + Download button
- ViolationDetail page wired:
  - Back button navigates to `/home`
  - Fetches `GET /v1/chassis/{id}` on mount
  - Renders two CameraCards (Cam1, Cam2) side by side
  - Decision buttons POST to `/v1/chassis/{id}/decision`
  - Flag toggle POSTs to `/v1/chassis/{id}/flag`
  - Download button fetches JSON bundle (v1)
- Debug images loaded from `/v1/debug/{measurement_id}` with lazy load + fallback placeholder

### Files to Create
```
frontend/src/components/CameraCard.tsx
frontend/src/components/DetailPanel.tsx
```

### Test Gate
- [ ] Detail page renders both camera cards with images
- [ ] Condition status shown per camera using StatusPill
- [ ] Correct/Incorrect buttons POST decision and update UI
- [ ] Flag toggle works and persists
- [ ] Back button returns to Dashboard
- [ ] Missing debug image shows fallback placeholder
- [ ] Vitest component tests for CameraCard and DetailPanel

---

## Phase 16 -- Full Integration + E2E Testing

**Goal**: Backend + frontend work together end-to-end. Playwright smoke tests pass.

### Deliverables
- Backend serves frontend `/dist` at root `/` path (static file mount in FastAPI or nginx)
- Vite build integrated into Docker multi-stage build
- Playwright E2E smoke tests:
  - Flow A: Dashboard loads -> table populates -> row click navigates to detail page
  - Flow B: Violation Detail renders both camera images -> decision can be recorded
- Full curl walkthrough documented in `docs/api.md`

### Files to Create
```
frontend/tests/e2e/dashboard.spec.ts
frontend/tests/e2e/violation-detail.spec.ts
frontend/playwright.config.ts
docs/api.md
```

### Test Gate
- [ ] `make build` produces a single Docker image with both backend + frontend
- [ ] Docker image starts and serves the Dashboard at `http://localhost:8000/home`
- [ ] API calls from the frontend work without CORS issues (same-origin)
- [ ] Playwright Flow A passes
- [ ] Playwright Flow B passes
- [ ] `make test` (backend) + `npm test` (frontend) all green
- [ ] Full end-to-end: start session -> drop images -> see results in Dashboard -> click row -> see detail page -> record decision

---

## Phase 17 -- Production Hardening & Deployment

**Goal**: Ready for staging deployment and production rollout.

### Deliverables
- Finalised `Dockerfile` (multi-stage, non-root user, healthcheck)
- Production `docker-compose.yml` template (from architecture.txt Section 14)
- `scripts/replay_session.py` tested against staging
- Graceful shutdown verified under load
- Security review: mTLS config documented, `AUTH_ENABLED` toggle, no PII in logs, no secrets logged
- Documentation updated: `docs/trd_doc.txt` (if any deviations), `CLAUDE.md`, `docs/api.md`
- Git tags + CD pipeline tested

### Files to Create
```
docker-compose.prod.yml
docs/runbook.md
```

### Test Gate
- [ ] Staging deploy: `docker compose up` with production-like config
- [ ] Replay script processes a day of images with expected accuracy
- [ ] `make eval` meets all accuracy targets (MAE <= 0.05 mm)
- [ ] Graceful shutdown: SIGTERM during active session completes cleanly
- [ ] `/v1/ready` returns 200 only when all dependencies are healthy
- [ ] No secrets in logs, no stack traces to clients
- [ ] CI/CD pipeline: tag push -> build -> push image -> deploy to staging

---

## Summary: Phase Dependencies

```
Phase  0: Scaffold          (no deps)
Phase  1: Config            (depends on 0)
Phase  2: Data Layer        (depends on 0)
Phase  3: CV Pipeline       (depends on 1, 2)
Phase  4: Persistence       (depends on 0)
Phase  5: Aggregator        (depends on 4)
Phase  6: SSE Broker        (depends on 0)
Phase  7: Watchers+Consumer (depends on 2, 3, 4, 5, 6)
Phase  8: Session+API       (depends on 5, 6, 7)
Phase  9: Observability     (depends on 8)
Phase 10: Eval Harness      (depends on 3)
Phase 11: Backend Hardening (depends on 8, 9, 10)
Phase 12: Frontend Scaffold (depends on 0)
Phase 13: Frontend API+SSE  (depends on 12)
Phase 14: Dashboard         (depends on 13)
Phase 15: Violation Detail  (depends on 13)
Phase 16: Integration+E2E  (depends on 11, 14, 15)
Phase 17: Production        (depends on 16)
```

**Parallelization opportunities**:
- Phases 1, 2, 4 can run in parallel after Phase 0
- Phases 5, 6 can run in parallel after Phase 4
- Phase 10 can start as soon as Phase 3 is done (parallel with 4-9)
- Phases 12-15 (frontend) can start as soon as Phase 0 is done and run in parallel with backend phases, but full integration (Phase 16) requires Phase 11

---

## User Story Mapping

| Phase | P0 Stories Covered | P1 Stories Enabled |
|-------|-------------------|-------------------|
| 0-1   | US-09 (API contract, partial) | -- |
| 2     | US-18 (bad filenames) | -- |
| 3     | Core of US-02, US-03 (measurement) | -- |
| 4-5   | US-07, US-08 (traceability) | -- |
| 6-8   | US-01, US-02, US-03, US-06, US-09, US-10 | US-11, US-12, US-28 |
| 9     | -- | -- |
| 10    | -- | US-17 (algo_params promotion) |
| 12-15 | US-04, US-05 (UI) | US-19, US-14, US-15, US-16 |
| 16-17 | All P0 complete | Ready for P1 sprint |
