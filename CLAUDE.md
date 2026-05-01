# Trailing Arm Detection

Classical computer-vision service that measures the **innermost circle diameter** on a trailing-arm component, using dual-camera images (left + right). **No machine learning.** A session-based API starts folder monitoring; per-camera and per-chassis results stream to the frontend dashboard in real time via Server-Sent Events.

This is the project memory file. Read this first in every session. Every sprint, update it.

---

## Domain and approach

- **Domain:** Manufacturing quality inspection / dimensional measurement.
- **Technique:** Classical CV only — `Gaussian blur → adaptive Gaussian threshold (inverted) → morphological close → external contours (largest-first) → masked HoughCircles constrained to target radius band → mm conversion → band-based classification`. See `docs/decisions/ADR-008.md` for the switch from the earlier Canny+RANSAC approach.
- **No ML. Not even a small one.** If a task seems to benefit from a learned model, **stop and ask the user** before adding any ML dependency. This constraint is recorded in `docs/decisions/ADR-001.md` and is a hard architectural boundary.
- **Deterministic pipeline.** Same input → same output, always. Every measurement record pins `algo_params_version` and `calibration_version`.

---

## Critical rules

### Always
- Keep the measurement pipeline (`src/tad/processing/`) **pure** — no DB, no logging beyond debug, no filesystem, no sessions. It takes an image and returns a result.
- Pin versions in `configs/algo_params/<version>.yaml`. **Never** edit an existing version; bump to a new one (`algo-1.3.0` → `algo-1.4.0`) and add an ADR.
- Parse the chassis number from the **filename** using `src/tad/ingestion/filename_parser.py`. The regex is the contract — do not change it without coordinating with Plant Engineering and adding an ADR.
- Use `asyncio.to_thread(...)` for CV work in async routes. OpenCV releases the GIL, so this gives real parallelism.
- Write to Postgres and MinIO **only** through the repository classes in `src/tad/persistence/repositories.py`.
- Use `structlog` for all logs. Every log record should carry `session_id`, `measurement_id`, `chassis_no`, and `camera_side` where applicable.
- Type-hint every public function. Use Pydantic models for every API and config boundary.
- Use fixed random seeds (`numpy.random.default_rng(seed=...)`) inside the pipeline. **Never** use global RNG state.

### Never
- **Never** run `uvicorn` with more than one worker. Session state is in-memory and must not be sharded across processes. If scaling is needed, revisit the architecture — do not silently add workers.
- **Never** introduce `localStorage`, `sessionStorage`, GPU dependencies (`torch`, `onnxruntime-gpu`, etc.), or any ML framework.
- **Never** write production code inside `notebooks/`. Notebooks are exploration only and must not be imported from `src/`.
- **Never** mutate `algo_params` or `calibration` objects at runtime. They are loaded once at startup and treated as immutable.
- **Never** log the chassis number in `info` / `warn` logs in plaintext. Hash it for those levels; plaintext is allowed only in local `debug` logs.
- **Never** commit anything under `data/`, `models/`, or `.env`. These are gitignored for a reason.
- **Never** reach the network in unit tests. Integration tests may use the local Postgres + MinIO from `docker-compose`.

---

## Tech stack (pinned)

| Purpose | Package | Version |
|---|---|---|
| Runtime | Python | 3.11.x |
| Web framework | FastAPI | 0.115.x |
| ASGI server | Uvicorn | 0.32.x |
| SSE helper | sse-starlette | 2.1.x |
| Computer vision | opencv-python | 4.10.x |
| Numerics | numpy | 1.26.x |
| Geometry helpers (optional) | scikit-image | 0.24.x |
| Filesystem watching | watchdog | 5.0.x |
| ORM | SQLAlchemy | 2.0.x (async) |
| Postgres driver | psycopg[binary] | 3.2.x |
| Blob storage | minio | 7.2.x |
| Schema validation | pydantic | 2.9.x |
| Settings | pydantic-settings | 2.x |
| YAML | PyYAML | 6.0.x |
| Logging | structlog | current |
| Metrics | prometheus-client | current |
| Tests | pytest + pytest-asyncio | 8.3.x |
| Property tests | hypothesis | current |
| Lint/format | ruff | 0.7.x |
| Types | mypy | 1.13.x |

Lock file is `uv.lock` (or `poetry.lock` — confirm with `pyproject.toml`).

---

## Key paths

```
configs/algo_params/        # versioned YAML; current is referenced by ALGO_PARAMS_VERSION
configs/calibration/        # one YAML per (camera_side, date); pointed at by env
src/tad/                    # the package
src/tad/main.py             # uvicorn entrypoint
src/tad/config/             # Settings, AlgoParams, Calibration loaders
src/tad/api/                # FastAPI app, routes, schemas, SSE
src/tad/workers/            # manager, runtime, consumer, aggregator, watcher, broker
src/tad/ingestion/          # filename_parser, image_validator, safe_read
src/tad/processing/        # PURE CV pipeline — no I/O
                            # preprocessing.py, threshold.py, contour_detect.py,
                            # confidence.py, annotate.py, pipeline.py, models.py
src/tad/persistence/        # SQLAlchemy models, repositories, MinIO store, migrations
src/tad/observability/      # logging config, Prometheus collectors
src/tad/evals/              # locked eval harness
tests/                      # mirrors src/tad/
tests/fixtures/             # committed small images + calibration YAMLs for tests
scripts/                    # calibration, replay, eval utilities
docs/decisions/             # ADRs — numbered, immutable once accepted
docs/trd.txt                # Technical Requirements Document (authoritative on "must")
docs/prd.txt                # Product Requirements Document
docs/architecture.txt       # end-to-end build guide
```

---

## Run commands

All entrypoints are via `make`. If you need to add a new one, add it here too.

```
make up              # docker compose: postgres + minio
make down            # stop the dev stack
make migrate         # alembic upgrade head
make seed            # seed dev data (fixtures)
make serve           # uvicorn with --reload on :8000
make test            # ruff + mypy + pytest (unit + integration)
make test-unit       # pytest tests/unit
make test-integration  # pytest tests/integration (needs `make up`)
make eval            # run the locked eval harness; produce a report
make lint            # ruff + mypy, no formatting changes
make format          # ruff format + isort
make build           # docker build, tag with git SHA
```

If a command you need doesn't exist, prefer adding a Makefile target over inventing a one-off shell incantation. This keeps the entrypoints stable.

---

## Environment setup

Local dev uses a `.env` file at the repo root. A template is in `.env.example`. Required variables:

```
DB_DSN=postgresql+psycopg://tad:tad@localhost:5432/tad
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=tad-debug
IMAGES_LEFT_DIR=/tmp/tad/images/left
IMAGES_RIGHT_DIR=/tmp/tad/images/right
ALGO_PARAMS_VERSION=algo-1.3.0
DEFAULT_CALIBRATION_LEFT=configs/calibration/cal-2026-03-14-L.yaml
DEFAULT_CALIBRATION_RIGHT=configs/calibration/cal-2026-03-14-R.yaml
ASYMMETRY_THRESHOLD_MM=0.15
QUEUE_MAX_SIZE=256
LOG_LEVEL=INFO
```

To kick the tires locally:

```bash
make up && make migrate
make serve

# drop fixture images into the watched folders
cp tests/fixtures/images/MALBB51BLPM123456_L.jpg /tmp/tad/images/left/
cp tests/fixtures/images/MALBB51BLPM123456_R.jpg /tmp/tad/images/right/

# start a session
curl -X POST http://localhost:8000/v1/sessions/start \
    -H "content-type: application/json" \
    -d '{"started_by":"dev"}'
```

---

## Coding conventions

### Python style
- Ruff is the source of truth for lint and format. If ruff disagrees with you, ruff wins.
- Import order: stdlib → third-party → first-party (`tad.*`). Ruff enforces this.
- Line length: 100 chars. Enforced by ruff.
- Prefer `from pathlib import Path` over `os.path`. Prefer `datetime.now(UTC)` over naive datetimes.
- Enums or `Literal[...]` for fixed-vocabulary fields (status, camera_side). Never bare strings.

### Typing
- Type hints on **every** public function — anything imported from another module.
- Private helpers may skip hints if obvious, but prefer to include them.
- Run `mypy --strict` on `src/tad/` (allowed exemptions tracked in `pyproject.toml`).

### Pydantic
- All API request/response models live in `src/tad/api/schemas.py`.
- All config models live in `src/tad/config/`.
- Domain dataclasses (pipeline I/O, internal events) use `@dataclass(frozen=True)` — not Pydantic — to keep the hot path light.

### Async
- Handlers and repositories are `async def`.
- CPU-bound CV work is wrapped in `await asyncio.to_thread(...)`.
- Never `time.sleep()` in an async context. Use `asyncio.sleep()`.
- Never do blocking file I/O from an async handler. Use `asyncio.to_thread` or an executor.

### Errors
- Raise domain exceptions (`NoCalibrationError`, `SessionNotActiveError`, `BadFilename`, etc.) from `src/tad/api/errors.py`.
- The API exception handler maps them to `ERR_*` codes. Do not hand-craft error JSON in routes.
- No stack traces to clients. Ever.

### Logging
- `structlog` with JSON output.
- Bind context (`session_id`, `measurement_id`, `chassis_no`, `camera_side`) using `log.bind(...)` rather than formatting into messages.
- Use `log.exception(...)` only in a real exception branch.

---

## Testing conventions

- `pytest-asyncio` mode is `auto`. Test functions can be `async def` without decorators.
- Fixtures live in `tests/fixtures/` and are committed. Small images and real calibration YAMLs only.
- Time is passed in, not taken. Classes that need "now" accept a `clock: Callable[[], datetime]` parameter.
- Unit tests must not reach the network or start containers.
- Integration tests may use the local Postgres + MinIO via `docker-compose`. Skip them with `-m "not integration"` when offline.
- Every bug fix ships with a test that would have caught it.
- The eval harness (`make eval`) is the final gate for any change to `src/tad/processing/` or `configs/algo_params/`. A PR that regresses MAE fails CI.

### Test layout
```
tests/unit/                 # fast, no network, no containers
tests/integration/          # real Postgres + MinIO, local watcher
tests/fixtures/             # images, YAMLs, database seeds
tests/benchmark/            # the locked eval set + accuracy gates (was tests/eval/)
```

---

## Database conventions

- All IDs are UUIDs generated **client-side** (Python `uuid4()`), not by the DB. This makes idempotency retries safe.
- All timestamps are `TIMESTAMPTZ` in UTC.
- Measurement records are **append-only** at the application layer. Corrections are new rows with a `corrects_measurement_id` field (not implemented in v1 — add when needed).
- Migrations live in `src/tad/persistence/migrations/versions/`. Generate with `alembic revision --autogenerate -m "<message>"`. Review the generated SQL before committing.
- Never use SQLAlchemy's synchronous engine. The project is async end-to-end.

---

## API conventions

- All routes live under `/v1/`. Breaking changes require `/v2/` and a migration plan.
- Request and response bodies are Pydantic models. No `dict[str, Any]` on the wire.
- Error envelope: `{ "error_code", "error_message", "request_id" }`. Set up once in the exception handler.
- `request_id` is generated middleware-side; logged on every record; returned in every response header (`X-Request-Id`) and body on errors.
- SSE events are named: `session_opened`, `camera_result`, `chassis_result`, `warning`, `session_closed`. Do not add new event types without updating the frontend contract.
- mTLS and a service token in `X-Service-Token` are required for production. In local dev, auth is disabled via `AUTH_ENABLED=false`.

---

## Common "how do I" workflows

### Adding a new algorithm-parameter version
1. Copy the current YAML: `cp configs/algo_params/algo-1.3.0.yaml configs/algo_params/algo-1.4.0.yaml`.
2. Edit the new file. Bump `version:` at the top.
3. Add an ADR in `docs/decisions/` explaining what changed and why.
4. Update `ALGO_PARAMS_VERSION` in `.env.example` (keep actual deploys' env untouched; ops promotes explicitly).
5. Run `make eval` and commit the before/after metrics in the PR description.

### Adding a new API route
1. Add the Pydantic schemas to `src/tad/api/schemas.py`.
2. Add the route function in the appropriate `src/tad/api/routes_*.py` file.
3. Wire dependencies via `Depends(get_...)` from `src/tad/api/deps.py`.
4. Add happy-path + two error-path integration tests in `tests/integration/`.
5. Update `docs/api.md`.

### Adding a new repository method
1. Add the method signature to the repository class (e.g. `MeasurementRepository`).
2. Add a unit-level test that exercises the method against the real Postgres in `tests/integration/`.
3. Never inline SQL outside the repository. If a raw query is needed, put it behind a method.

### Adding a new pipeline stage
1. Place it in its own file under `src/tad/processing/`.
2. Keep the function signature `f(image_or_intermediate, params) -> next_intermediate`. **No I/O.**
3. Add it to `pipeline.py` with a named step.
4. Write unit tests with synthetic inputs.
5. Re-run `make eval` — if MAE regresses, either revert or update the eval thresholds (with reviewer sign-off).

### Investigating a production chassis result
1. `GET /v1/measurements/{id}` or search by `chassis_no` through the QA view.
2. Open the debug image at `GET /v1/debug/{id}` — it shows the detected circle, the measurement, and the confidence.
3. The record pins `algo_params_version` and `calibration_version` so the measurement is fully reproducible.

---

## Gotchas and non-obvious things

- **Watcher thread ≠ event loop.** The `watchdog` library runs in its own threads. Always bridge to asyncio with `loop.call_soon_threadsafe(queue.put_nowait, item)`. Calling `queue.put_nowait` directly from the watcher thread is a data race.
- **Images may be half-written.** The capture system writes images to the folder, and `watchdog` can fire `on_created` before the write completes. The `safe_read.py` size-stability loop is not optional — it prevents the pipeline from ever seeing truncated JPEGs.
- **SSE slow subscriber = drop, not block.** If a dashboard client is slow, the broker drops it rather than back-pressuring the producer. A reconnecting client catches up via `GET /v1/sessions/{id}/results?since=<cursor>`. Do not "fix" this by making the producer wait.
- **One process only.** See the Always/Never list. If you are tempted to run multiple workers, you are solving the wrong problem — the pipeline is far faster than the capture cadence.
- **The detector is target-driven.** Hough is only allowed to accept circles whose radius falls within `target_diameter_mm ± radius_tolerance_mm`. This is what keeps the plate texture from producing phantom circles. If the real parts drift in size, the algo version must be bumped (new ADR, new YAML).
- **Contours are walked largest-first.** The inner dark hole is usually surrounded by a much larger bright plate contour on the inverted threshold, so the correct contour is picked early. Tight `hough.param2` is still important to reject noise inside the plate.
- **Camera side is L or R, always uppercase.** The filename parser normalises to uppercase. Do not add lowercase handling downstream — if you see lowercase, the parser is broken.
- **Chassis number is 5 chars, VIN-format (no I, O, Q).** The regex is in `filename_parser.py`. If real chassis numbers start including O or Q, this is a contract-breaking change and needs an ADR.

---

## Branch and commit conventions

- **Branch:** `phase-NN/short-description-vN` (e.g. `phase-04/ransac-refinement-v1`).
- **Commits:** Conventional Commits.
  - `feat(measure): add RANSAC refinement for sub-pixel accuracy`
  - `fix(parser): reject filenames with less than 5 characters`
  - `docs(adr): add ADR-007 for asymmetry threshold bump`
  - `test(aggregator): cover orphan-chassis flush path`
  - `chore(deps): bump opencv-python to 4.10.0.84`
- **PRs:** Small, focused. One logical change per PR. If a PR touches `src/tad/processing/` or `configs/algo_params/`, paste the `make eval` output in the description.

---

## Glossary

- **Trailing arm** — the suspension component under inspection.
- **Innermost circle** — smallest-radius circular feature in the central region of the trailing-arm image; the geometry being measured.
- **Chassis number** — 5-character string format identifier, parsed from the filename.
- **Camera side** — `L` (left) or `R` (right).
- **Session** — interval between `/sessions/start` and `/sessions/{id}/stop`. All folder monitoring and event emission happen inside a session.
- **Per-camera result** — measurement from one image.
- **Chassis result** — aggregate across both camera sides for one chassis.
- **Asymmetry** — absolute difference between the left and right measurements (mm).
- **Calibration** — the `mm_per_px` factor for a specific camera at a point in time.
- **CLAHE** — Contrast-Limited Adaptive Histogram Equalisation.
- **Hough Circle** — classical voting-based circle detector (`cv2.HoughCircles`).
- **RANSAC** — Random Sample Consensus; robust fitter used here to refine circle params to sub-pixel accuracy on edge points.
- **SSE** — Server-Sent Events; uni-directional HTTP event stream for the live dashboard.
- **algo_params** — versioned YAML of algorithm hyperparameters.
- **ADR** — Architecture Decision Record, in `docs/decisions/`.

---

## Reference documents

Keep these up to date when the system changes materially. If this CLAUDE.md contradicts one of them, the other document wins:

- `docs/trd.txt` — Technical Requirements Document v2.0 (authoritative on *what must be true*).
- `docs/prd.txt` — Product Requirements Document v1.0 (user stories, UX, release plan).
- `docs/architecture.txt` — End-to-end architecture and build guide.
- `docs/decisions/ADR-00*.md` — individual architecture decisions. Numbered, immutable once accepted.
- `docs/api.md` — human-readable API reference (generated from OpenAPI + hand-written notes).

When in doubt about a requirement, check the TRD. When in doubt about a user-facing behaviour, check the PRD. When in doubt about an implementation choice, check the relevant ADR.