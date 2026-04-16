# Trailing Arm Detection -- Implementation Plan (Demo Path)

> **Status**: Phases 0-3 complete; Phases 4-7 scoped for the demo deliverable.
> **Last updated**: 2026-04-17
>
> This plan covers the build from greenfield to a working, tested,
> demo-ready backend + frontend that satisfies the P0 user stories in
> `docs/user_stories.txt` and the measurement accuracy targets in
> `docs/trd_doc.txt`.
>
> Phases 0-3 have been delivered and tested; they are summarised here
> for traceability and are **not re-executed**. Phases 4-7 are the
> remaining demo work, consolidated from the original 17-phase plan
> so one engineer can ship the demo in a small number of focused
> iterations.

---

## Phases 0-3 -- COMPLETED

| Phase | Scope | Branch / Commit | Test coverage |
|-------|-------|-----------------|---------------|
| **0** | Project scaffold, Docker, Makefile, CI workflow, `/v1/health` | `master` (commit 709c43f) | repo builds, `/v1/health` returns 200 |
| **1** | Config layer: Settings, AlgoParams, Calibration, `/v1/ready` | `master` (commit 709c43f) | 12 unit tests |
| **2** | Data layer: filename parser, image validator, safe read, domain errors | `phase-02/data-layer-v1` (commit bc2617a) | 39 unit tests |
| **3** | Measurement pipeline (contour + masked Hough, ADR-008, `algo-1.3.0`) | `phase-03/contour-detection-v2` (commit e1dca17) | 45 unit tests; validated on real images cam18jdleofhtlhj6 pair |

**Total**: **96 unit tests passing**, ruff + mypy clean on 27 source files.

Key outputs from Phase 3:
- `src/tad/measurement/` contains the full pure CV pipeline.
- `configs/algo_params/algo-1.3.0.yaml` is the active algorithm version.
- `docs/decisions/ADR-008.md` records the switch from the earlier Canny+RANSAC approach.
- Real-image smoke test: both cameras measure the bushing at ~20 mm with 0.4 mm asymmetry.

---

## Phase 4 -- Backend API + Storage + Sessions

**Goal**: The full backend is running. Start a session by HTTP, drop image pairs into the watched folders, and see per-camera and per-chassis events stream out over SSE with rows landing in Postgres and debug JPEGs in MinIO.

This phase consolidates the original Phases 4-9: persistence, aggregator, SSE broker, folder watchers, consumer loop, session manager, API routes, and basic observability.

### Deliverables

**Persistence** (`src/tad/persistence/`)
- `db.py` -- async SQLAlchemy engine + session maker
- `models.py` -- SQLAlchemy mapped classes for `sessions`, `measurements`, `chassis_records`, `calibrations`
- `repositories.py` -- `SessionRepository`, `MeasurementRepository`, `ChassisRepository` (async)
- `blob_store.py` -- `DebugImageStore` backed by MinIO
- `migrations/versions/001_initial_schema.py` -- Alembic migration creating the four tables (client-side UUIDs, TIMESTAMPTZ, indexes per TRD Section 5)

**Session machinery** (`src/tad/sessions/`)
- `aggregator.py` -- `Aggregator` with the TRD 7.1 status matrix and the `somewhat_ok_band_mm > asymmetry_threshold_mm` downgrade
- `broker.py` -- `SseBroker` with slow-subscriber drop (no back-pressure to producer)
- `watcher.py` -- `FolderWatcher` over `watchdog`, bridging via `loop.call_soon_threadsafe`
- `consumer.py` -- `process_item()` pipeline: safe_read -> parse_filename -> validate_image -> `asyncio.to_thread(measure_innermost_diameter)` -> upload debug blob -> insert measurement -> publish SSE -> `aggregator.accept`
- `runtime.py` -- `SessionRuntime` dataclass holding per-session state
- `manager.py` -- `SessionManager` with `start()` / `stop()` / `require_active()`

**API** (`src/tad/api/`)
- `app.py` -- FastAPI factory with lifespan, error-envelope handler, request-ID middleware
- `deps.py` -- `Depends()` wiring
- `schemas.py` -- all Pydantic request/response models
- `routes_sessions.py` -- `POST /v1/sessions/start`, `POST /v1/sessions/{id}/stop`, `GET /v1/sessions/{id}/events` (SSE), `GET /v1/sessions/{id}/results`
- `routes_chassis.py` -- `GET /v1/chassis`, `GET /v1/chassis/{id}`, `POST /v1/chassis/{id}/decision`, `POST /v1/chassis/{id}/flag`
- `routes_dashboard.py` -- `GET /v1/dashboard/summary`
- `routes_measurements.py` -- `GET /v1/measurements/{id}`, `GET /v1/debug/{id}`
- Health/ready routes (already exist, extend `/ready` to include DB + MinIO checks)

**Observability** (`src/tad/observability/`)
- `logging_conf.py` -- `structlog` JSON config with chassis-number hashing at info level
- Request-ID middleware (generated, logged, returned in `X-Request-Id`)
- Defer Prometheus metrics to Phase 7 unless trivially free

### Files to create
```
src/tad/persistence/{db,models,repositories,blob_store}.py
src/tad/persistence/migrations/env.py
src/tad/persistence/migrations/versions/001_initial_schema.py
alembic.ini
src/tad/sessions/{aggregator,broker,watcher,consumer,runtime,manager}.py
src/tad/api/{app,deps,schemas,middleware}.py
src/tad/api/routes_{sessions,chassis,dashboard,measurements}.py
src/tad/observability/logging_conf.py
scripts/seed_db.py
tests/unit/test_aggregator.py
tests/unit/test_broker.py
tests/integration/test_repositories.py
tests/integration/test_blob_store.py
tests/integration/test_session_flow.py
tests/integration/test_api_routes.py
```

### Test gate
- [ ] `make up && make migrate` creates all four tables.
- [ ] Unit tests cover every cell of the status matrix, the asymmetry downgrade, orphan flush, and slow-subscriber drop.
- [ ] Integration test: `POST /start` -> drop two fixture images -> receive `camera_result` x2 + `chassis_result` x1 over SSE -> `POST /stop` returns a summary with `pass/review/fail/error` counts.
- [ ] `GET /v1/chassis?status=...&page=1` and `GET /v1/chassis/{id}` return the documented shapes (TRD 8.4, 8.5).
- [ ] `POST /v1/chassis/{id}/decision` and `/flag` persist and round-trip.
- [ ] `GET /v1/dashboard/summary` returns the KPI payload (TRD 8.8).
- [ ] `GET /v1/debug/{id}` streams the annotated JPEG.
- [ ] Error envelope: every non-2xx returns `{error_code, error_message, request_id}`; no stack traces ever reach the client.
- [ ] `make test` green (unit + integration).

### Maps to user stories / TRD
US-01, US-02, US-03, US-06, US-07, US-08, US-09, US-10, US-11 (missing-side highlight in events), US-18 (bad-filename warnings). TRD Sections 5, 7, 8, 9.

---

## Phase 5 -- Frontend Application

**Goal**: Operators can open the browser, see the dashboard light up in real time, click a row, and use the violation detail page. No mock data anywhere.

This phase consolidates the original Phases 12-15.

### Deliverables

**Scaffold** (`frontend/`)
- `package.json` with pinned deps (TRD 10.2): React 18.3, Vite 5.4, Tailwind 3.4, Recharts 2.12, React Router 6.26, @tanstack/react-table 8.20, Axios 1.7, lucide-react 0.441, @headlessui/react 2.1, date-fns 3.6, TypeScript 5.5
- `vite.config.ts` with `/v1` proxy to `:8000`
- `tailwind.config.ts`, `tsconfig.json`, `postcss.config.cjs`, `index.html`
- `src/main.tsx`, `src/App.tsx`, `src/routes.ts`
- `src/labels.ts` -- single source of truth for status/camera UI labels (TRD 10.3)

**Shared components** (`frontend/src/components/`)
- `Header.tsx` (shared nav, "Live View"/"Settings" as placeholders for v1)
- `StatusPill.tsx` (uses `labels.ts`)

**API layer** (`frontend/src/api/` + `hooks/`)
- `client.ts` -- Axios instance
- `dashboard.ts`, `chassis.ts`, `sessions.ts`, `sse.ts`
- `useLiveSession.ts` -- EventSource wrapper, reconnects with backoff, tracks last event + connected state
- `useChassisList.ts` -- paged chassis list with filters
- `SessionContext` in `App.tsx`

**Dashboard page** (`frontend/src/pages/Dashboard.tsx`)
- `KpiDonut.tsx` (Recharts PieChart - Violations Today)
- `KpiTrend.tsx` (Recharts LineChart - Violation Trend, two lines)
- `AlertsList.tsx` (clickable, navigates to detail)
- `FiltersBar.tsx` (Today / Past 7 Days / Date Range, shift, condition, search, CSV export)
- `ProductionTable.tsx` (@tanstack/react-table, sortable, clickable rows)
- `Pagination.tsx`
- Live wiring: on `chassis_result`, prepend row and refetch KPI summary
- Empty state: "Waiting for the first chassis. Session started at HH:MM..."

**Violation Detail page** (`frontend/src/pages/ViolationDetail.tsx`)
- `CameraCard.tsx` -- Cam1/Cam2 header, debug image (lazy load), condition pill, Correct/Incorrect decision buttons
- `DetailPanel.tsx` -- KV list, Flagged toggle, Download button (JSON bundle in v1)

### Files to create
```
frontend/package.json, vite.config.ts, tailwind.config.ts, tsconfig.json,
  postcss.config.cjs, index.html
frontend/src/{main.tsx,App.tsx,routes.ts,labels.ts}
frontend/src/styles/index.css
frontend/src/components/{Header,StatusPill,KpiDonut,KpiTrend,AlertsList,
  FiltersBar,ProductionTable,Pagination,CameraCard,DetailPanel}.tsx
frontend/src/pages/{Dashboard,ViolationDetail}.tsx
frontend/src/api/{client,dashboard,chassis,sessions,sse}.ts
frontend/src/hooks/{useLiveSession,useChassisList}.ts
frontend/tests/unit/{labels,StatusPill,KpiDonut}.test.ts
.github/workflows/ci-frontend.yml
```

### Test gate
- [ ] `cd frontend && npm install && npm run dev` boots Vite on :5173.
- [ ] `/home` renders the full Dashboard with live data coming from a running backend.
- [ ] Dropping image pairs into the watched folders prepends rows to the Production Details table within ~500 ms.
- [ ] KPI cards refresh when a `chassis_result` event arrives.
- [ ] Row click navigates to `/home/details/:id` and both camera images load from `/v1/debug/...`.
- [ ] Correct / Incorrect buttons POST to `/v1/chassis/{id}/decision` and the UI reflects the chosen state.
- [ ] Flagged toggle and JSON download both work.
- [ ] Vitest component tests for StatusPill (PASS/REVIEW/FAIL/ERROR -> correct label + colour) and KpiDonut pass.
- [ ] `npm run build` produces a static bundle in `frontend/dist`.

### Maps to user stories / TRD
US-02, US-04, US-05 (UI side), US-12, US-19. TRD Section 10 (Frontend Architecture).

---

## Phase 6 -- End-to-End Integration + Demo Readiness

**Goal**: One Docker image ships both services, the demo walkthrough runs cleanly on a fresh clone, and at least one Playwright flow proves the whole pipeline.

This phase consolidates the original Phases 10, 11, 16.

### Deliverables

**Same-origin deployment**
- Backend serves `frontend/dist/` from `/` with SPA fallback.
- `/v1/*` stays reserved for the API.

**Docker**
- `Dockerfile` finalised: multi-stage build (Node 20 -> Python 3.11-slim), non-root user, healthcheck on `/v1/ready`.
- `docker-compose.yml` production-like stack (Postgres + MinIO + tad service + mounted image folders).
- `make build` produces a tagged image.

**Minimal eval harness** (P0 slice only; the full locked-set runner stays on the backlog)
- `src/tad/evals/eval.py` -- reads `tests/eval/dataset.csv` (seeded with the two real-image fixtures), runs the pipeline, computes MAE / P95 / max error, prints a report.
- `make eval` target.

**Smoke tests**
- Playwright: (a) Dashboard loads, table populates, row click opens detail page; (b) Detail page renders both camera images and records a decision.
- `scripts/replay_session.py` -- drops a fixture pair into the watched folders for manual demo runs.

**Docs**
- `docs/api.md` -- curl walkthrough for each P0 route.
- `README.md` -- "Run the demo in 5 minutes" section:
  1. `cp .env.example .env`
  2. `make up && make migrate`
  3. `make serve` (backend) and `make dev-ui` (frontend) -- or `make build && docker run ...`
  4. `python scripts/replay_session.py`
  5. Open `http://localhost:8000/home` and watch rows appear.

### Test gate
- [ ] `make build` produces a single image that serves the Dashboard at `http://localhost:8000/home`.
- [ ] Full walkthrough in the README works on a fresh clone.
- [ ] Both Playwright flows pass.
- [ ] `make eval` produces a report.
- [ ] All backend unit + integration tests still green.
- [ ] No CORS errors, no dev-only URLs in the built bundle.

### Maps to user stories / TRD
US-09 (OpenAPI spec exposed), US-28 (auto-reconnect via the existing SSE hook). TRD Sections 10.11, 15 (infrastructure), 18 (testing).

---

## Phase 7 -- (Optional) Production Hardening

**Goal**: Deploy-ready, not just demo-ready. Execute **only** after the demo lands.

Scope pulled from the original Phases 9, 11, 17 (the parts that are *not* required for a demo):

- Full `structlog` + `/metrics` Prometheus instrumentation (TRD Section 20 monitoring).
- Graceful shutdown under SIGTERM with in-flight drain.
- Idempotency guard on `(session_id, path, mtime)`.
- mTLS + `X-Service-Token` + `AUTH_ENABLED` plumbing.
- Calibration promotion workflow + `scripts/run_calibration.py`.
- CI/CD: `cd.yml` tag-push pipeline, staging replay gate.
- Admin panel (US-22), CSV export (US-14), shift/weekly rollups (US-13), calibration-health indicator (US-21).
- Full locked eval harness with fail-on-regression CI gate (TRD Section 18.1).

None of this blocks the demo. Split into its own TRD-driven iteration.

---

## Phase summary

```
COMPLETED:
  Phase 0 -- Scaffold
  Phase 1 -- Config
  Phase 2 -- Data layer
  Phase 3 -- Measurement pipeline (algo-1.3.0, ADR-008)

DEMO PATH:
  Phase 4 -- Backend API + Storage + Sessions      [~backend only]
  Phase 5 -- Frontend Application                  [~frontend only]
  Phase 6 -- E2E Integration + Demo Readiness      [the ship]

OPTIONAL LATER:
  Phase 7 -- Production Hardening
```

### Parallelisation

- Phase 4 and Phase 5 can run in parallel once Phase 4's API schemas (`schemas.py`) are stubbed -- frontend can develop against a mocked backend (MSW) while backend finishes the routes.
- Phase 6 requires both.

### P0 user-story coverage after demo

All P0 stories from `docs/user_stories.txt` are covered by the end of Phase 6:

- US-01 Start -> Phase 4
- US-02 Live feed -> Phases 4 + 5
- US-03 Chassis aggregate -> Phase 4
- US-04 Status at a glance -> Phase 5
- US-05 Annotated image -> Phases 4 + 5
- US-06 Stop + summary -> Phase 4
- US-07 Chassis lookup -> Phase 4
- US-08 Traceability -> Phase 4 (already pinned from Phase 3 in the schema)
- US-09 Documented API -> Phases 4 + 6
- US-10 Start-failure handling -> Phase 4 + 5
- US-18 Bad-filename warnings -> Phases 4 + 5
