# TAD Frontend

React + Vite + Tailwind dashboard for the Trailing Arm Detection service.
Two pages: `/home` (Dashboard) and `/home/details/:id` (Violation Detail),
both wired to the backend's `/v1/*` REST API and the `/v1/sessions/{id}/events`
SSE stream.

## Prerequisites

- **Node.js 20+** (tested with Node 22.x) and **npm 10+**
- The backend running on `http://localhost:8000` (or the Vite proxy will
  fail to reach `/v1/*`)

## Quick start on your system

```bash
# 1. Install dependencies (first time only, ~2 minutes)
cd frontend
npm install

# 2. Run the Vitest unit/component suite — no backend needed
npm test
# => 27 tests across 7 files should pass

# 3. Production build (outputs to frontend/dist)
npm run build

# 4. Type-check only
npm run typecheck
```

Or with the project Makefile from the repo root:

```bash
make install-ui      # first time
make test-ui         # runs Vitest
make build-ui        # production build
```

## Running the dashboard against a live backend

You need two terminals.

**Terminal 1 — start the backend** (Phase 4 service):

```bash
# From the repo root
make up                          # Postgres + MinIO via docker compose
make migrate                     # alembic upgrade head (first time only)
python scripts/seed_db.py        # optional: seed some rows
python -m uvicorn tad.main:app --reload --host 0.0.0.0 --port 8000
```

If you don't have Docker, the backend still starts with in-memory stores
if you pass `create_app(session_repo=..., meas_repo=..., ...)` manually
(see `tests/integration/conftest.py` for the pattern).

**Terminal 2 — start the frontend dev server**:

```bash
make dev-ui
# or
cd frontend && npm run dev
```

Open **<http://localhost:5173/home>** in your browser. The Vite dev server
proxies every `/v1/*` request to `http://localhost:8000`, so the dashboard
hits the real backend.

## Exercising the full loop manually

With both servers running:

```bash
# Kick off a session
curl -X POST http://localhost:8000/v1/sessions/start \
    -H 'content-type: application/json' \
    -d '{"started_by":"me","shift":"A","area":"Welding"}'
# {"session_id": "<SID>", "status": "ACTIVE", ...}

# Drop matched images into the watched folders
cp tests/fixtures/images/cam18jdleofhtlhj6_L.jpg /tmp/tad/images/left/ABC12345678901234_L.jpg
cp tests/fixtures/images/cam18jdleofhtlhj6_R.jpg /tmp/tad/images/right/ABC12345678901234_R.jpg

# Watch the dashboard — the Production Details table updates live
# via the SSE stream, the KPI cards refetch, and clicking a row
# opens the Violation Detail page.

# Stop the session when you're done
curl -X POST http://localhost:8000/v1/sessions/<SID>/stop
```

## What the tests cover

| File | Covers |
|------|--------|
| `tests/unit/labels.test.ts` | Status/camera terminology mapping (TRD 10.3) |
| `tests/unit/StatusPill.test.tsx` | All four status -> label + colour, accessible name |
| `tests/unit/Header.test.tsx` | Nav tabs, live indicator states |
| `tests/unit/KpiDonut.test.tsx` | Legend labels, counts, centre violation % |
| `tests/unit/CameraCard.test.tsx` | Image rendering, decision buttons, placeholder |
| `tests/unit/Pagination.test.tsx` | Prev/next enable state, page-change callback |
| `tests/unit/api.test.ts` | API client hits the right URLs with the right params |

Run them with:

```bash
npm test           # one-shot
npm run test:watch # watch mode
```

## Directory layout

```
frontend/
├── index.html
├── vite.config.ts           # dev server + /v1 proxy + Vitest config
├── tailwind.config.ts
├── tsconfig.json
├── package.json
└── src/
    ├── main.tsx             # ReactDOM.createRoot
    ├── App.tsx              # <BrowserRouter> + routes
    ├── routes.ts            # route constants
    ├── labels.ts            # single source of truth for UI labels
    ├── styles/index.css     # Tailwind entry point
    ├── api/                 # axios client + typed helpers + SSE
    ├── hooks/               # useLiveSession, useChassisList
    ├── components/
    │   ├── Header.tsx
    │   ├── StatusPill.tsx
    │   ├── KpiDonut.tsx
    │   ├── KpiTrend.tsx
    │   ├── AlertsList.tsx
    │   ├── FiltersBar.tsx
    │   ├── ProductionTable.tsx
    │   ├── Pagination.tsx
    │   ├── CameraCard.tsx
    │   └── DetailPanel.tsx
    └── pages/
        ├── Dashboard.tsx
        └── ViolationDetail.tsx
```

## Troubleshooting

**`npm install` is slow** — First-time install downloads ~300 packages; 1-3
minutes is normal on a typical connection.

**`/v1/*` requests fail** — Check the backend is on `localhost:8000` and
the Vite proxy is reading `vite.config.ts`. Use the browser DevTools
Network tab; failed requests are the ones going to `/v1/...`.

**SSE shows "Reconnecting…"** — The backend is unreachable or the session
was stopped. Check the backend logs for errors.

**Recharts warnings in tests** — `The width(0) and height(0) of chart
should be greater than 0` is cosmetic: jsdom has no layout engine, so
Recharts can't measure its container. The charts still render and the
tests still pass.
