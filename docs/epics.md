# Trailing Arm Detection — Epic → Story → Task Backlog

Status snapshot (2026-04-17): Phases 0–6 complete. Single-container Docker
demo runs end-to-end on `docker compose up`. Postgres + schema available
behind the `prod` profile but app still runs in in-memory demo mode.

This document is the authoritative work breakdown. It is derived from:

- `docs/prd_doc.txt` — product requirements
- `docs/trd_doc.txt` — technical requirements
- `docs/architecture.txt` — end-to-end build guide
- `docs/decisions/ADR-001..009.md` — architecture decisions
- `PLAN.md` / `C:\Users\shradha\.claude\plans\*.md` — phase plans
- `CLAUDE.md` — coding standards, critical rules, conventions

Convention: **EPIC-n** → **STORY-n.m** → **TASK-n.m.k**. Status icons:
✅ done · 🟡 partial · ⬜ not started.

---

## Table of contents

| Epic | Title | Phases | Status |
|---|---|---|---|
| EPIC-1 | Project Foundation & Configuration | 0, 1 | ✅ |
| EPIC-2 | Data Ingestion Layer | 2 | ✅ |
| EPIC-3 | Classical CV Measurement Pipeline | 3 | ✅ |
| EPIC-4 | Session Orchestration & Aggregation | 4 | ✅ |
| EPIC-5 | Persistence Layer (Postgres + MinIO) | 4 | ✅ |
| EPIC-6 | HTTP API & SSE Surface | 4 | ✅ |
| EPIC-7 | Frontend Dashboard | 5 | ✅ |
| EPIC-8 | Demo Mode Infrastructure | 5.5 | ✅ |
| EPIC-9 | Quality Gate — Tests, Eval, E2E | 6 | ✅ |
| EPIC-10 | Docker Deployment & Ops | 6 | ✅ |
| EPIC-11 | Production Hardening | 7 | ✅ |
| EPIC-12 | Calibration & Drift Management | 7 | ⬜ |
| EPIC-13 | QA Correction & Flag Workflow | 8 | 🟡 |
| EPIC-14 | Observability & SLOs | 9 | ⬜ |

---

# EPIC-1 — Project Foundation & Configuration

**Status**: ✅ Complete (Phases 0 + 1)
**Goal**: A fresh clone must build, lint, and start a stub FastAPI server; all
algorithm and hardware constants must load from versioned YAML.
**Acceptance**:
- `make lint`, `make test-unit`, `make serve` succeed on a clean repo.
- `curl http://localhost:8000/v1/health` returns `200`.
- Algorithm parameters and camera calibrations load from YAML and are
  treated as immutable at runtime.
**Why**: Establishes the packaging, tooling, and configuration skeleton every
downstream epic builds on. Without it, CI, reproducible builds, and
deterministic measurements are impossible.

## STORY-1.1 — Python packaging and tooling scaffold  ✅
As a platform engineer, I need a pinned, reproducible Python environment so
that every developer and CI run resolves the same dependency tree.

- **TASK-1.1.1** ✅ `pyproject.toml` with `hatchling` backend, Python 3.11,
  all runtime deps pinned per CLAUDE.md table (fastapi 0.115.x, uvicorn,
  sse-starlette, opencv-python, numpy, watchdog, sqlalchemy, psycopg,
  minio, pydantic, pydantic-settings, pyyaml, structlog, prometheus-client).
- **TASK-1.1.2** ✅ `[project.optional-dependencies] dev` = pytest,
  pytest-asyncio, hypothesis, ruff, mypy, httpx, alembic.
- **TASK-1.1.3** ✅ Ruff config: line-length=100, isort grouping
  (stdlib / third-party / first-party `tad.*`). Per-file ignores:
  `tests/**/*.py = B008`, `src/tad/api/*.py = B008`.
- **TASK-1.1.4** ✅ Mypy `strict` scope = `src/tad/`, exemptions tracked
  in `[tool.mypy.overrides]`.
- **TASK-1.1.5** ✅ `[tool.pytest.ini_options] asyncio_mode = "auto"`.

## STORY-1.2 — Repo hygiene and developer UX  ✅
As a developer, I need one command to spin up, migrate, and serve the app so
that onboarding takes minutes not hours.

- **TASK-1.2.1** ✅ `.gitignore` covering `data/`, `models/`, `.env`,
  `__pycache__`, `.venv`, `*.egg-info`, `node_modules/`, `dist/`,
  `frontend/test-results/`, `frontend/playwright-report/`.
- **TASK-1.2.2** ✅ `.env.example` containing every variable consumed by
  `Settings` (DB_DSN, MINIO_*, IMAGES_*_DIR, ALGO_PARAMS_VERSION,
  DEFAULT_CALIBRATION_*, ASYMMETRY_THRESHOLD_MM, QUEUE_MAX_SIZE,
  LOG_LEVEL, AUTH_ENABLED).
- **TASK-1.2.3** ✅ `Makefile` targets: `up`, `down`, `migrate`, `seed`,
  `serve`, `demo`, `demo-seed`, `test`, `test-unit`, `test-integration`,
  `eval`, `lint`, `format`, `build`, `dev-ui`, `install-ui`, `test-ui`,
  `build-ui`.
- **TASK-1.2.4** ✅ `.pre-commit-config.yaml` (ruff lint + format, mypy).
- **TASK-1.2.5** ✅ `.github/workflows/ci-backend.yml` — ruff + mypy +
  pytest on every push / PR.

## STORY-1.3 — Configuration layer (Settings, AlgoParams, Calibration)  ✅
As an operator, I need to change the active algorithm version or camera
calibration by editing a file, not by redeploying code.

- **TASK-1.3.1** ✅ `src/tad/config/settings.py` — Pydantic-Settings class,
  one field per `.env.example`, `functools.lru_cache`-wrapped
  `get_settings()`.
- **TASK-1.3.2** ✅ `src/tad/config/algo_params.py` — nested Pydantic models
  (`CLAHEParams`, `BlurParams`, `ThresholdParams`, `MorphologyParams`,
  `ContourParams`, `HoughParams`, `TargetParams`, `ToleranceParams`,
  `ConfidenceParams`). `load_algo_params(version, base_dir)` reads
  `configs/algo_params/<version>.yaml`.
- **TASK-1.3.3** ✅ `src/tad/config/calibration.py` — `Calibration` model
  (calibration_id, camera_side as `Literal["L","R"]`, mm_per_px, method,
  valid_from, operator, reference_image). `load_calibration(path)`.
- **TASK-1.3.4** ✅ Committed YAMLs: `configs/algo_params/algo-1.2.0.yaml`
  (initial), `algo-1.3.0.yaml` (post-ADR-008 contour+Hough), per-side
  calibration files under `configs/calibration/`.
- **TASK-1.3.5** ✅ Unit tests: `tests/unit/test_settings.py`,
  `test_algo_params.py`, `test_calibration.py` — valid load + missing
  file + malformed YAML + camera-side mismatch.

## STORY-1.4 — Minimal FastAPI app + health + readiness  ✅
As an SRE, I need `/v1/health` and `/v1/ready` so load balancers and
monitors can distinguish "process alive" from "dependencies healthy".

- **TASK-1.4.1** ✅ `src/tad/main.py` — uvicorn entrypoint wiring prod
  repositories.
- **TASK-1.4.2** ✅ `src/tad/api/routes_health.py` — `/v1/health` = 200
  always; `/v1/ready` = 200 only if both calibrations load + both
  watched dirs exist.
- **TASK-1.4.3** ✅ `RequestIdMiddleware` in `src/tad/api/middleware.py`
  — set `X-Request-Id` header + bind to structlog context.
- **TASK-1.4.4** ✅ `ADR-001` recording the "classical CV only, no ML"
  hard constraint.

---

# EPIC-2 — Data Ingestion Layer

**Status**: ✅ Complete (Phase 2)
**Goal**: Safely extract chassis identity from filenames, verify image
integrity, and accept paired L/R writes without racing half-written files.
**Acceptance**:
- Filenames matching the VIN-prefixed regex parse to
  `(chassis_no, camera_side, sequence?)`; everything else raises
  `BadFilename`.
- `safe_read()` never returns a partially-written buffer.
- A paired `*_L` / `*_R` drop on different timestamps still resolves to
  one logical chassis through the aggregator.
**Why**: The filename is the system's only link between an image on disk
and a chassis in the plant — getting it wrong silently mis-labels
production data forever.

## STORY-2.1 — Chassis-number filename parser  ✅
As a line-side operator, I need the system to recognise files named
`MALBB51BLPM123456_L.jpg` (and `_L_1.jpg` retakes) so that my images are
routed to the correct camera side and chassis.

- **TASK-2.1.1** ✅ `src/tad/data/filename_parser.py` — regex
  `^[A-HJ-NPR-Z0-9]{17}_[LR](?:_\d+)?\.(?:jpg|jpeg|png)$` (VIN-compliant,
  no I/O/Q).
- **TASK-2.1.2** ✅ Raises `BadFilename` from `src/tad/api/errors.py` on
  any deviation; normalises camera_side to upper case.
- **TASK-2.1.3** ✅ Hypothesis property tests + explicit fixture tests
  for every failure mode.

## STORY-2.2 — Safe (size-stable) image read  ✅
As a reliability engineer, I need the pipeline to never process a
truncated JPEG so that we never emit "NO_DETECTION" for a file that was
simply still being written when the watcher fired.

- **TASK-2.2.1** ✅ `src/tad/data/safe_read.py` — 3-sample size-stability
  loop (sleep-poll-compare), timeout configurable, returns bytes or
  raises `ReadFail`.
- **TASK-2.2.2** ✅ `src/tad/data/image_validator.py` — OpenCV decode
  check, min resolution, channel count, aspect-ratio sanity band.
- **TASK-2.2.3** ✅ Integration test that writes a file in two chunks
  and verifies `safe_read` waits.

---

# EPIC-3 — Classical CV Measurement Pipeline

**Status**: ✅ Complete (Phase 3, post-ADR-008 switch)
**Goal**: Given one image and a calibration, produce a single sub-pixel
diameter-in-mm with a status band and a confidence score — no I/O, no
state.
**Acceptance**:
- `measure_innermost_diameter(PipelineInput)` is pure, deterministic,
  and lives under 500 ms on the reference hardware for 2048×1536.
- `make eval` reports MAE / P95 / max error against the committed
  dataset and exits non-zero on regression beyond the demo gate.
**Why**: The pipeline is the product. Everything else exists to feed it
images and carry its output.

## STORY-3.1 — Preprocessing  ✅
- **TASK-3.1.1** ✅ `preprocessing.py` — Gaussian blur (kernel from
  algo_params), optional CLAHE (disabled in algo-1.3.0).

## STORY-3.2 — Adaptive threshold + morphology  ✅
- **TASK-3.2.1** ✅ `threshold.py` — adaptive Gaussian threshold
  (inverted), block_size + C from params.
- **TASK-3.2.2** ✅ Morphological close, kernel_size + iterations
  parametrised.

## STORY-3.3 — Contour walk (largest-first)  ✅
- **TASK-3.3.1** ✅ `contour_detect.py` — external contours, area
  filter `contour.min_area`, sort descending.
- **TASK-3.3.2** ✅ For each candidate: compute bounding ROI, build
  mask, pass to masked HoughCircles.

## STORY-3.4 — HoughCircles constrained to target radius band  ✅
- **TASK-3.4.1** ✅ Hough dp / min_dist / param1 / param2 from
  `HoughParams`; min/max radius derived from
  `target_diameter_mm ± radius_tolerance_mm / mm_per_px`.
- **TASK-3.4.2** ✅ First accepted circle wins; fall through contours
  until one matches or we return `NO_DETECTION`.

## STORY-3.5 — Band-based status classification  ✅
- **TASK-3.5.1** ✅ `evaluate_status(diameter_mm, params) → "PASS" |
  "REVIEW" | "FAIL"` using `ok_band_mm`, `somewhat_ok_band_mm`.
- **TASK-3.5.2** ✅ Tolerance min/max outer guardrails for hard FAIL.

## STORY-3.6 — Confidence score  ✅
- **TASK-3.6.1** ✅ `confidence.py` — composite from contour
  circularity, Hough accumulator strength, radius residual.

## STORY-3.7 — Annotated debug image  ✅
- **TASK-3.7.1** ✅ `annotate.py` — draws detected circle, radius arrow,
  status band on a copy of the input; returned as `bytes` (JPEG).

## STORY-3.8 — Pipeline assembly  ✅
- **TASK-3.8.1** ✅ `pipeline.py` wires every stage and emits
  `PipelineOutput` (frozen dataclass).
- **TASK-3.8.2** ✅ `models.py` — `PipelineInput`, `PipelineOutput` —
  both `@dataclass(frozen=True)`.
- **TASK-3.8.3** ✅ Fixed `numpy.random.default_rng(seed=...)` where RNG
  is used; never touch global state.

## STORY-3.9 — Algorithm-switch ADR and version bump  ✅
- **TASK-3.9.1** ✅ `ADR-008.md` documenting the switch from
  Canny+RANSAC to contour+Hough; `algo-1.3.0.yaml` committed as the
  replacement.

---

# EPIC-4 — Session Orchestration & Aggregation

**Status**: ✅ Complete (Phase 4)
**Goal**: A session owns folder watchers, an async queue, a consumer loop,
an L/R aggregator, and an SSE broker. Lifecycle: `start → running →
stop`. One session per process.
**Acceptance**:
- `POST /v1/sessions/start` boots watchers + consumer within 500 ms.
- Per-camera and per-chassis events reach SSE subscribers within
  250 ms of pipeline completion.
- Orphan L or R after configurable timeout flushes as partial chassis
  with warning.
**Why**: This is where real-time plant flow becomes a structured,
observable stream.

## STORY-4.1 — Folder watcher bridged to asyncio  ✅
- **TASK-4.1.1** ✅ `sessions/watcher.py` — watchdog `Observer` per side,
  hands events to the event loop via
  `loop.call_soon_threadsafe(queue.put_nowait, ...)`.
- **TASK-4.1.2** ✅ Known-limitation doc (ADR-009): Windows
  `ReadDirectoryChangesW` buffer can drop events under rapid cadence;
  replay bypasses the watcher.

## STORY-4.2 — Consumer loop (CV work on a worker thread)  ✅
- **TASK-4.2.1** ✅ `sessions/consumer.py` — pulls from queue, wraps
  pipeline in `await asyncio.to_thread(...)`, writes the measurement
  row + debug blob via repositories, emits `camera_result` SSE event.

## STORY-4.3 — L/R aggregator + status matrix  ✅
- **TASK-4.3.1** ✅ `sessions/aggregator.py` — pairs per-camera results
  by `chassis_no`, emits `chassis_result` with combined status via a
  4×4 L/R matrix, downgrades PASS → REVIEW when
  `|d_L - d_R| > asymmetry_threshold_mm`.
- **TASK-4.3.2** ✅ Orphan timeout flush with `warning` event.

## STORY-4.4 — SSE broker with slow-subscriber drop  ✅
- **TASK-4.4.1** ✅ `sessions/broker.py` — per-subscriber bounded queue,
  drop instead of back-pressure, integer cursor so clients can
  reconnect via `GET /v1/sessions/{id}/results?since=N`.

## STORY-4.5 — Session manager  ✅
- **TASK-4.5.1** ✅ `sessions/manager.py` — constructs watchers,
  consumer, aggregator, broker; single active session held on
  `app.state`; `start()` / `stop()` / `status()`.

---

# EPIC-5 — Persistence Layer

**Status**: ✅ Complete (Phase 4)
**Goal**: Durable append-only measurement + chassis records in Postgres;
debug JPEGs in MinIO keyed by measurement_id.
**Acceptance**:
- All IDs are Python-side `uuid4()` (idempotent retries).
- All timestamps `TIMESTAMPTZ` UTC.
- No direct SQL outside the repository classes.
**Why**: Production QA needs every measurement reproducible months
later — pinning `algo_params_version` + `calibration_version` per row
is the contract.

## STORY-5.1 — SQLAlchemy ORM + schema migration  ✅
- **TASK-5.1.1** ✅ `persistence/models.py` — ORM classes:
  `SessionORM`, `MeasurementORM`, `ChassisRecordORM`, `CalibrationORM`;
  mirror `@dataclass` DTOs (`SessionRow`, `MeasurementRow`,
  `ChassisRow`).
- **TASK-5.1.2** ✅ Alembic migration `001_initial_schema.py`
  (5 tables + indexes on `chassis_no`, `session_id`, `processed_at`).
- **TASK-5.1.3** ✅ `alembic.ini` + `persistence/migrations/env.py`
  loading DSN from `Settings`.

## STORY-5.2 — Async repositories  ✅
- **TASK-5.2.1** ✅ `persistence/repositories.py` — Protocols
  (`SessionRepository`, `MeasurementRepository`, `ChassisRepository`)
  + SQL implementations using `AsyncSession` factory.
- **TASK-5.2.2** ✅ `persistence/db.py` — `build_engine(dsn)` +
  `build_session_factory(engine)`.

## STORY-5.3 — Debug blob store  ✅
- **TASK-5.3.1** ✅ `persistence/blob_store.py` — `DebugImageStore`
  Protocol with `MinIOStore` + `InMemoryBlobStore` implementations.
- **TASK-5.3.2** ✅ Key scheme: `<year>/<month>/<day>/<measurement_id>.jpg`.

## STORY-5.4 — Test-double in-memory fakes  ✅
- **TASK-5.4.1** ✅ `tests/fakes.py` — `InMemorySessionRepository`,
  `InMemoryMeasurementRepository`, `InMemoryChassisRepository` that
  satisfy every Protocol. Used by unit + integration + demo runs.

---

# EPIC-6 — HTTP API & SSE Surface

**Status**: ✅ Complete (Phase 4)
**Goal**: `/v1/*` REST + SSE endpoints contracted in `docs/api.md`.
**Acceptance**:
- Every route has Pydantic request + response models.
- Errors return `{error_code, error_message, request_id}`.
- SSE event names are the fixed set: `session_opened`,
  `camera_result`, `chassis_result`, `warning`, `session_closed`.
**Why**: The frontend and any external integration live and die by this
contract — strict typing keeps both honest.

## STORY-6.1 — Route modules  ✅
- **TASK-6.1.1** ✅ `routes_sessions.py` — start / stop / status.
- **TASK-6.1.2** ✅ `routes_chassis.py` — list + detail.
- **TASK-6.1.3** ✅ `routes_measurements.py` — detail + debug image.
- **TASK-6.1.4** ✅ `routes_dashboard.py` — KPI aggregates + trend
  series.
- **TASK-6.1.5** ✅ `routes_health.py` — already covered by Epic 1.
- **TASK-6.1.6** ✅ `routes_demo.py` — demo replay start / stop /
  status (see Epic 8).

## STORY-6.2 — SSE channel  ✅
- **TASK-6.2.1** ✅ `/v1/sessions/{id}/events` via `sse-starlette`,
  heartbeat every 10 s.
- **TASK-6.2.2** ✅ Catch-up via `GET /results?since=<cursor>`.

## STORY-6.3 — Dependency injection + error envelope  ✅
- **TASK-6.3.1** ✅ `api/deps.py` — `get_session_manager`,
  `get_chassis_repo`, etc., all resolved from `app.state`.
- **TASK-6.3.2** ✅ `api/errors.py` — `TadError` base + subclasses +
  exception handler registration.

## STORY-6.4 — API reference documentation  ✅
- **TASK-6.4.1** ✅ `docs/api.md` — every P0 route, curl examples,
  error-code table, `/v1/demo/*` section.

---

# EPIC-7 — Frontend Dashboard

**Status**: ✅ Complete (Phase 5)
**Goal**: A shop-floor-grade SPA that mirrors the current session in real
time, lets QA drill into a chassis, correct a violation, and flag.
**Acceptance**:
- `/` redirects to `/home` showing KPIs, trend chart, alerts, and
  production details table.
- Row click → `/home/details/<chassis_record_id>` with Cam1/Cam2
  panes + Correct Violation + Flag.
- `/home/live` renders the live session status matrix.
**Why**: PRD story 3 — "a plant manager should see violations appear
within seconds, without refreshing".

## STORY-7.1 — Build + toolchain  ✅
- **TASK-7.1.1** ✅ Vite + React 18 + TypeScript + Tailwind CSS.
- **TASK-7.1.2** ✅ TanStack Table, Recharts, react-router-dom.
- **TASK-7.1.3** ✅ Vitest + Testing Library; Playwright via
  separate `tests/e2e/`.

## STORY-7.2 — Dashboard page  ✅
- **TASK-7.2.1** ✅ KPI cards: Violations Today, Violation Trend,
  Recent Alerts, Production Details.
- **TASK-7.2.2** ✅ Trend chart via Recharts.
- **TASK-7.2.3** ✅ Chassis table with pagination, row click → detail
  route.

## STORY-7.3 — Violation Detail page  ✅
- **TASK-7.3.1** ✅ CameraCard (×2) — image, overlay, diameter,
  status chip, Correct Violation button.
- **TASK-7.3.2** ✅ Chassis info panel with measurement metadata.
- **TASK-7.3.3** ✅ Flag toggle.
- **TASK-7.3.4** ✅ Back-to-dashboard nav.

## STORY-7.4 — Live View  ✅
- **TASK-7.4.1** ✅ Status matrix keyed by session state + SSE
  subscription.

## STORY-7.5 — API client  ✅
- **TASK-7.5.1** ✅ `src/api/*.ts` — thin typed fetch wrappers, one
  module per backend router.

---

# EPIC-8 — Demo Mode Infrastructure

**Status**: ✅ Complete (Phase 5.5)
**Goal**: Zero-friction local demo — one command, no Docker, no DB, no
manual folder creation.
**Acceptance**:
- `python scripts/run_demo.py` boots a fully working app on :8000.
- Dashboard auto-triggers replay from `yca_valid` (321 pairs) at 20 s
  cadence and shows a mix of PASS / REVIEW / FAIL.
- Replay bypasses the Windows watcher to avoid
  `ReadDirectoryChangesW` buffer overflow (ADR-009).
**Why**: Stakeholder walk-throughs and dev iteration — the production
wiring requires Docker + Postgres + real folders, which is a 15-minute
yak-shave on a fresh Windows box.

## STORY-8.1 — In-memory app runner  ✅
- **TASK-8.1.1** ✅ `scripts/run_demo.py` — builds `Settings` with
  throwaway DSN, wires in-memory repositories + blob store, applies
  widened algo-1.3.0 overlay (target 20 mm, ok=1.0, somewhat_ok=1.5,
  asymmetry=2.5).

## STORY-8.2 — Replay API  ✅
- **TASK-8.2.1** ✅ `src/tad/api/routes_demo.py` — `POST
  /v1/demo/replay/start` (source_dir, interval_seconds, max_pairs),
  `/stop`, `/status`.
- **TASK-8.2.2** ✅ `_drive_one(rt, side, path)` feeds the consumer
  inline (bypasses watchdog).
- **TASK-8.2.3** ✅ VIN-compliant chassis-number generator
  (`DMAX` + base-32 index, no I/O/Q).

## STORY-8.3 — Dashboard auto-start  ✅
- **TASK-8.3.1** ✅ `frontend/src/pages/Dashboard.tsx` useEffect —
  poll `/v1/demo/replay/status`, call `/start` if idle, banner while
  streaming.

## STORY-8.4 — Supporting scripts  ✅
- **TASK-8.4.1** ✅ `scripts/seed_demo.py` — manual burst of paired
  images into the watched folders.
- **TASK-8.4.2** ✅ `docs/demo_walkthrough.md` — step-by-step local
  test plan.
- **TASK-8.4.3** ✅ `ADR-009.md` documenting the demo-mode split and
  watcher bypass.

---

# EPIC-9 — Quality Gate — Tests, Eval, E2E

**Status**: ✅ Complete (Phase 6)
**Goal**: Every code path has an automated test; the measurement
pipeline has an accuracy gate; the UI has a smoke test.
**Acceptance**:
- Backend: ruff + mypy + pytest (unit + integration) green;
  145 tests pass.
- Frontend: vitest green (27 tests); Playwright E2E green (3 specs).
- `make eval` runs and enforces a demo gate (`max ≤ 1.0 mm`).
**Why**: Without this, any change to the measurement pipeline silently
regresses production.

## STORY-9.1 — Unit + integration test suites  ✅
- **TASK-9.1.1** ✅ `tests/unit/` — parser, validator, safe_read,
  pipeline stages, status logic, filename regex properties, config
  loaders.
- **TASK-9.1.2** ✅ `tests/integration/` — API via `TestClient` +
  in-memory fakes; session start → pair drop → SSE assertion.

## STORY-9.2 — Eval harness  ✅
- **TASK-9.2.1** ✅ `src/tad/evals/eval.py` — CSV loader, per-row
  runner, MAE / P95 / max summariser, TRD §16 gates + relaxed demo
  gate; exit 1 on fail.
- **TASK-9.2.2** ✅ `tests/eval/dataset.csv` — committed fixture
  dataset (cam18 pairs, caliper values).

## STORY-9.3 — Frontend unit tests  ✅
- **TASK-9.3.1** ✅ `frontend/tests/unit/**/*.spec.tsx` — Dashboard,
  CameraCard, ChassisTable, API client mocks.

## STORY-9.4 — Playwright E2E  ✅
- **TASK-9.4.1** ✅ `playwright.config.ts` — chromium, baseURL
  `:5173`, `PLAYWRIGHT_BASE_URL` env override.
- **TASK-9.4.2** ✅ `tests/e2e/dashboard.spec.ts` — `/` → `/home`
  redirect + KPI assertions + row-click navigation.
- **TASK-9.4.3** ✅ `tests/e2e/violation_detail.spec.ts` — seed 1
  chassis, click Correct Violation, toggle Flag.
- **TASK-9.4.4** ✅ Vitest `include` / `exclude` so unit runner
  ignores E2E suite.

---

# EPIC-10 — Docker Deployment & Ops

**Status**: ✅ Complete (this session)
**Goal**: A single `docker compose up -d` boots the full app on
`:8000` from a clean host; no Python venv, no npm, no manual folder
creation.
**Acceptance**:
- `docker compose up -d` → `tad-app` becomes **healthy** within 20 s.
- `http://localhost:8000` serves the built UI + API from one port.
- Replay reads from the bind-mounted `yca_valid` fixture folder.
**Why**: Makes the service "clone-and-run" for new developers,
stakeholder demos, and downstream deploys.

## STORY-10.1 — Multi-stage Dockerfile  ✅
- **TASK-10.1.1** ✅ Stage 1 `node:20-alpine` — `npm ci` +
  `npm run build` → `/build/dist`.
- **TASK-10.1.2** ✅ Stage 2 `python:3.11-slim` — install system libs
  (`libgl1`, `libglib2.0-0`, `curl`), `pip install .`, copy src +
  configs + scripts + tests/fakes + `tests/fixtures/images` +
  frontend/dist + alembic.ini.
- **TASK-10.1.3** ✅ Non-root user `tad` (uid 1000); `EXPOSE 8000`;
  `HEALTHCHECK` via `/v1/health`; `CMD ["python",
  "scripts/run_demo.py"]`.
- **TASK-10.1.4** ✅ `ENV PYTHONPATH=/app/src` so `alembic` and ad-hoc
  `python -m tad.*` calls work.

## STORY-10.2 — Compose orchestration  ✅
- **TASK-10.2.1** ✅ `tad` service — build from Dockerfile,
  `0.0.0.0:8000`, bind-mount `./tests/fixtures/test_images:ro`,
  `restart: unless-stopped`, per-container healthcheck.
- **TASK-10.2.2** ✅ `postgres` + `minio` services gated behind
  `profiles: ["prod"]` so they don't start by default; named volumes
  `pgdata` / `miniodata`.
- **TASK-10.2.3** ✅ `.dockerignore` — drops node_modules, .venv,
  caches, .git, `tests/fixtures/test_images` (mounted at runtime).

## STORY-10.3 — Landing-page documentation  ✅
- **TASK-10.3.1** ✅ `README.md` — 5-minute quickstart, architecture
  overview, core command table, docs index.
- **TASK-10.3.2** ✅ Single-port deploy section (after `npm run build`
  the `:8000` uvicorn serves UI + API).

## STORY-10.4 — Architecture documentation  ✅
- **TASK-10.4.1** ✅ `docs/architecture_diagram.md` — 12 Mermaid
  diagrams (component, data flow, session lifecycle, SSE, etc.).

---

# EPIC-11 — Production Hardening  ✅

**Status**: Complete (this session)
**Goal**: Make the container safe to deploy past "demo on a laptop" —
real persistence, TLS, secrets, rate limits, API gating.
**Acceptance**:
- `docker compose --profile prod up` boots tad + postgres + minio
  with `tad.main:app` entrypoint; all chassis/measurements persist
  to Postgres; debug JPEGs land in MinIO.
- `/v1/demo/*` is compiled out of the production image.
- mTLS + `X-Service-Token` enforced when `AUTH_ENABLED=true`.
**Why**: The TRD §3 security + availability requirements and the
ADR-009 negative-consequences list both block prod rollout until this
lands.

## STORY-11.1 — Prod-mode container entrypoint  ✅
- **TASK-11.1.1** ✅ `src/tad/main.py` — `_default_app()` wires
  SqlSessionRepository / SqlMeasurementRepository / SqlChassisRepository
  + MinIOStore, mkdirs the watched folders, applies the wide-band
  demo overlay when `DEMO_ENABLED=true`.
- **TASK-11.1.2** ✅ `docker-compose.yml` — `tad` service depends on
  `postgres` + `minio` with `condition: service_healthy`; both
  dependencies carry their own healthchecks.
- **TASK-11.1.3** ✅ Compose `command: sh -c "alembic upgrade head &&
  exec uvicorn tad.main:app ..."` runs migrations before the app
  starts; bad migration = container exits rather than serving against
  a stale schema.

## STORY-11.2 — Gate demo routes behind a flag  ✅
- **TASK-11.2.1** ✅ `Settings.demo_enabled: bool = False` +
  `create_app()` gate; SPA fallback tightened to 404 on unmounted
  `/v1/*`.
- **TASK-11.2.2** ✅ `tests/unit/test_app_demo_gating.py` — routes
  absent (404 GET / 404-or-405 POST) when off, ReplayStatus schema
  returned when on.

## STORY-11.3 — Auth (service token)  ✅
- **TASK-11.3.1** ✅ `ServiceTokenMiddleware` (`src/tad/api/middleware.py`)
  — constant-time `hmac.compare_digest` against
  `Settings.allowed_tokens()`; exempt paths include /v1/health,
  /v1/ready, /docs, /assets/, /home, /.
- **TASK-11.3.2** ⬜ mTLS via uvicorn SSL flags — deferred; token
  auth is the MVP. Deploy behind a reverse proxy for TLS termination.
- **TASK-11.3.3** ✅ Middleware only installed when
  `settings.auth_enabled`; allowed_tokens empty = wide-open
  short-circuit (misconfig safety).

## STORY-11.4 — Image provenance  ✅
- **TASK-11.4.1** ✅ `make build` now tags `tad:latest` AND
  `tad:<short-sha>`.
- **TASK-11.4.2** ✅ `.env` never copied into the image; compose
  passes configuration via `environment:` block. Real secrets
  remain future-EPIC work (Docker secrets / SOPS).

---

# EPIC-12 — Calibration & Drift Management  ⬜

**Status**: Not started (Phase 7)
**Goal**: Calibration becomes a first-class, operator-driven workflow,
not a file the engineer hand-edits.
**Acceptance**:
- A new calibration can be captured, validated, and activated without
  a redeploy.
- Historical `calibrations` rows preserved forever; measurements
  pin the exact calibration id used.
**Why**: TRD §8 — measurement drift is the #1 production risk; today
swapping calibration requires editing YAML + restart.

## STORY-12.1 — Calibration capture API  ⬜
- **TASK-12.1.1** ⬜ `POST /v1/calibrations` — upload reference image
  + operator metadata; server computes mm_per_px, writes row, writes
  YAML snapshot.
- **TASK-12.1.2** ⬜ `POST /v1/calibrations/{id}/activate` — atomic
  swap of `DEFAULT_CALIBRATION_LEFT|RIGHT` pointer.

## STORY-12.2 — Drift monitor  ⬜
- **TASK-12.2.1** ⬜ Daily job computing moving mean of measured vs
  target; alert when drift > threshold.
- **TASK-12.2.2** ⬜ Metrics: `tad_calibration_drift_mm` gauge.

---

# EPIC-13 — QA Correction & Flag Workflow  🟡

**Status**: Partial (buttons exist, persistence wiring pending)
**Goal**: A QA operator can correct a false violation or flag a
chassis for follow-up; decisions are auditable.
**Acceptance**:
- Each decision creates an append-only row referencing the original
  measurement (PRD story 7).
- Corrections propagate to chassis-level status without mutating the
  source measurement.
**Why**: PRD §5 — auditability is mandatory for ISO-9001 compliance.

## STORY-13.1 — Decision schema  ⬜
- **TASK-13.1.1** ⬜ `decisions` table (decision_id, measurement_id,
  operator, kind ∈ {correct_violation, flag, unflag}, reason,
  created_at).
- **TASK-13.1.2** ⬜ Alembic migration + repository.

## STORY-13.2 — API + UI wiring  🟡
- **TASK-13.2.1** ✅ Frontend buttons render (Correct Violation,
  Flag).
- **TASK-13.2.2** ⬜ `POST /v1/measurements/{id}/decisions` persists
  the row.
- **TASK-13.2.3** ⬜ Chassis aggregate re-computes `overall_status`
  when a correction lands.

## STORY-13.3 — Audit log view  ⬜
- **TASK-13.3.1** ⬜ `GET /v1/chassis/{id}/decisions` timeline.
- **TASK-13.3.2** ⬜ Detail-page timeline panel.

---

# EPIC-14 — Observability & SLOs  ⬜

**Status**: Not started (Phase 9)
**Goal**: Every request and every measurement is visible in logs,
metrics, and traces; SLOs have dashboards.
**Acceptance**:
- `structlog` JSON logs carry session_id, measurement_id, chassis_no
  (hashed at info/warn), camera_side.
- `/metrics` Prometheus endpoint exposes pipeline latency
  histograms, queue depth, drop count, SSE subscriber count.
- Grafana dashboard committed as JSON in `docs/observability/`.
**Why**: TRD §10 — we need to answer "is the system healthy right
now?" without SSHing.

## STORY-14.1 — Structured logging  🟡
- **TASK-14.1.1** ✅ `observability/logging_conf.py` — `configure_logging`
  boots structlog.
- **TASK-14.1.2** ⬜ Hashing helper for `chassis_no` at info/warn
  levels (plaintext only in debug).

## STORY-14.2 — Prometheus metrics  ⬜
- **TASK-14.2.1** ⬜ `observability/metrics.py` — histograms for
  pipeline stages, queue gauge, drop counter, SSE connection
  gauge.
- **TASK-14.2.2** ⬜ `/metrics` route + Prometheus scrape config.

## STORY-14.3 — SLO dashboard  ⬜
- **TASK-14.3.1** ⬜ Grafana JSON committed under
  `docs/observability/grafana/`.
- **TASK-14.3.2** ⬜ Alert rules: p95 latency > 800 ms for 5 m,
  pipeline error rate > 2 % for 5 m.

---

## Appendix A — Cross-references

| Source | Where it lives |
|---|---|
| Phase plans | `PLAN.md` (historical), `C:\Users\shradha\.claude\plans\*.md` |
| Product requirements | `docs/prd_doc.txt` |
| Technical requirements | `docs/trd_doc.txt` |
| Architecture | `docs/architecture.txt`, `docs/architecture_diagram.md` |
| API reference | `docs/api.md` |
| Decisions | `docs/decisions/ADR-001..009.md` |
| User stories | `docs/user_stories.txt` |
| Coding rules | `CLAUDE.md` |

## Appendix B — Done-definition

A task is **Done** when all of the following hold:
1. Code + tests committed on a `phase-NN/...` branch with a
   Conventional-Commit message.
2. `make lint` + `make test` green locally and in CI.
3. If the task touches `src/tad/measurement/` or
   `configs/algo_params/` — `make eval` output is in the PR description.
4. The relevant doc (`api.md`, `architecture_diagram.md`, an ADR) is
   updated in the same PR.
