# Trailing Arm Detection

Classical computer-vision service that measures the innermost circle
diameter on a trailing-arm component from dual-camera images, exposes
per-camera and per-chassis results to operators in real time, and
provides a React dashboard with full traceability.

**No machine learning.** The detection pipeline is deterministic
classical CV (adaptive threshold → contours → masked Hough). See
[ADR-001](docs/decisions/ADR-001.md) and
[ADR-008](docs/decisions/ADR-008.md) for the rationale and the
algorithm switch.

![architecture](docs/architecture_diagram.md "Flow diagrams live here")

## Run the demo in 5 minutes

You need **Python 3.11+** and **Node.js 20+**. Docker is optional.

```bash
# 1. One-time: install dependencies
pip install -e ".[dev]"
cd frontend && npm install && cd ..

# 2. Start the backend (one terminal)
make demo
# ✓ uvicorn running on :8000
# ✓ auto-creates ~/.tad/images/{left,right}
# ✓ uses in-memory storage (no Docker required)

# 3. Start the frontend (second terminal)
make dev-ui
# ✓ Vite dev server on :5173 with /v1 proxy
```

Open **<http://localhost:5173/home>**. The Dashboard auto-calls
`/v1/demo/replay/start` — chassis rows appear every 20 seconds from
the committed `tests/fixtures/test_images/yca_valid/` (321 L+R pairs of
real trailing-arm photos).

Click any row → Violation Detail page with the actual industrial
photo, detected circle overlay, status pill, Correct/Incorrect decision
buttons, flag toggle, and JSON download.

For the full walkthrough with screenshots and troubleshooting, see
[`docs/demo_walkthrough.md`](docs/demo_walkthrough.md).

## Build and test

```bash
make test              # backend: ruff + mypy + pytest (145 tests)
make test-ui           # frontend: vitest (27 tests)
make eval              # eval harness (MAE / P95 / max error vs caliper)
make build-ui          # production frontend bundle (frontend/dist/)
make build             # Docker image (tagged with git SHA)

# Frontend end-to-end (requires `make demo` + `make dev-ui` running):
cd frontend && npm run test:e2e
```

Everything above runs from a fresh clone on Linux, macOS, or Windows
(Git Bash for the bash snippets).

## Single-port deploy

When `frontend/dist/` exists, the backend serves it at `/` with an SPA
fallback, so you don't need the Vite dev server at all:

```bash
make build-ui                   # produces frontend/dist/
make demo                       # one server on :8000 serves both
# Open http://localhost:8000/home
```

## Architecture

- **Backend** (FastAPI, uvicorn single-worker): session manager
  orchestrates filesystem watchers, a classical-CV measurement pipeline
  wrapped in `asyncio.to_thread`, a chassis aggregator, and an in-memory
  SSE broker. Persistence via SQLAlchemy async (`SqlSessionRepository`
  et al.) or in-memory fakes for demos and tests.
- **Frontend** (React 18 + Vite + TypeScript + Tailwind + Recharts):
  two pages — Dashboard (`/home`) and Violation Detail
  (`/home/details/:id`). All `/v1/*` calls proxied through Vite in dev;
  same-origin in production.
- **Measurement pipeline (algo-1.3.0)**: Gaussian blur → adaptive
  Gaussian threshold (inverted) → morph close → external contours
  largest-first → for each contour run `cv2.HoughCircles` constrained
  to `target_diameter_mm ± radius_tolerance_mm`. First matching circle
  wins. Classification into PASS / REVIEW / FAIL is band-based; no
  stochastic sampling anywhere.

Full flow diagrams:
[`docs/architecture_diagram.md`](docs/architecture_diagram.md)
(12 Mermaid diagrams covering system, runtime, session lifecycle,
per-image pipeline, CV stages, classification tree, aggregation,
SSE, demo replay, frontend tree, data model, deployment).

## Project layout

```
tad/
├── src/tad/               # Python backend
│   ├── api/               # FastAPI routers + schemas
│   ├── sessions/          # SessionManager, watchers, aggregator, broker
│   ├── measurement/       # pure CV pipeline (ADR-008)
│   ├── data/              # filename parser, image validator
│   ├── persistence/       # SQLAlchemy + MinIO + in-memory fakes
│   ├── config/            # Settings, AlgoParams, Calibration loaders
│   └── evals/             # locked eval harness
├── frontend/              # React SPA (Phase 5)
├── tests/
│   ├── unit/              # 96 backend unit tests
│   ├── integration/       # 49 backend HTTP + session-flow tests
│   ├── eval/              # locked eval dataset
│   └── fixtures/          # committed images + calibration YAMLs
├── scripts/
│   ├── run_demo.py        # in-memory boot, no Docker (ADR-009)
│   ├── seed_demo.py       # synthetic image burst
│   └── ...
├── configs/               # algo_params/algo-1.3.0.yaml + calibrations
└── docs/
    ├── architecture.txt
    ├── architecture_diagram.md
    ├── api.md
    ├── demo_walkthrough.md
    ├── trd_doc.txt / prd_doc.txt / user_stories.txt
    └── decisions/         # ADR-001 through ADR-009
```

## Core commands

| Command | What it does |
|---------|--------------|
| `make demo`        | Backend in demo mode (:8000, in-memory, no Docker) |
| `make demo-seed`   | Drop 5 synthetic chassis pairs for a fast demo |
| `make dev-ui`      | Frontend dev server (:5173, proxies /v1) |
| `make test`        | Backend ruff + mypy + pytest |
| `make test-ui`     | Frontend Vitest |
| `make eval`        | Eval harness (MAE vs caliper) |
| `make build-ui`    | Production frontend bundle |
| `make build`       | Docker image |
| `make up`          | Start Postgres + MinIO via docker-compose |
| `make migrate`     | Alembic upgrade head |
| `make serve`       | Backend with SQL + MinIO wiring (production) |
| `make lint`        | Ruff + format check + mypy |
| `make format`      | Apply ruff --fix + format |

## Documentation

- [`docs/demo_walkthrough.md`](docs/demo_walkthrough.md) —
  **start here** for end-to-end testing
- [`docs/api.md`](docs/api.md) — HTTP API reference with curl examples
- [`docs/architecture_diagram.md`](docs/architecture_diagram.md) —
  visual flow diagrams
- [`docs/architecture.txt`](docs/architecture.txt) — full build guide
- [`docs/trd_doc.txt`](docs/trd_doc.txt) — normative requirements
- [`docs/prd_doc.txt`](docs/prd_doc.txt) — user stories and product context
- [`docs/decisions/`](docs/decisions/) — 9 Architecture Decision Records
- [`CLAUDE.md`](CLAUDE.md) — project memory file (critical rules +
  conventions + gotchas)
- [`PLAN.md`](PLAN.md) — phase-by-phase implementation plan

## License

Internal — no license specified.
