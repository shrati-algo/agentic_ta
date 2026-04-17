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

### Option A — Demo mode (recommended, no Docker required)

In-memory storage. Perfect for UI smoke-tests; data resets on restart.

**Terminal 1 — backend in demo mode**:

```bash
# From the repo root
make demo
# or: python scripts/run_demo.py
```

This auto-creates the watched image folders at
`~/.tad/images/left` and `~/.tad/images/right` and starts uvicorn on
`:8000` with in-memory repositories + blob store. You should see:

```
TAD backend (DEMO MODE -- in-memory, no Docker required)
Image folder  (left):  C:\Users\you\.tad\images\left
Image folder  (right): C:\Users\you\.tad\images\right
...
Uvicorn running on http://0.0.0.0:8000
```

**Terminal 2 — frontend**:

```bash
make dev-ui
# or: cd frontend && npm run dev
```

Open **<http://localhost:5173/home>**.

### Option B — Full stack with Docker

Persistent Postgres + MinIO. Use this when you want to test the full
production wiring.

**Terminal 1** — make sure Docker Desktop is **running first**, then:

```bash
# One-time setup (only if you've never run the backend):
cp .env.example .env
mkdir -p /tmp/tad/images/left /tmp/tad/images/right   # macOS/Linux
# On Windows (Git Bash):
mkdir -p "$HOME/tad/images/left" "$HOME/tad/images/right"
# Then edit .env and set IMAGES_LEFT_DIR / IMAGES_RIGHT_DIR to those paths.

# Every time:
make up          # Postgres + MinIO
make migrate     # alembic upgrade head
python -m uvicorn tad.main:app --reload --port 8000
```

**Terminal 2** — same as Option A: `make dev-ui`.

## Exercising the full loop manually

With both servers running (demo mode paths shown; adjust if you used
Option B with different folders):

```bash
# 1. Kick off a session
curl -X POST http://localhost:8000/v1/sessions/start \
    -H 'content-type: application/json' \
    -d '{"started_by":"me","shift":"A","area":"Welding"}'
# {"session_id": "<SID>", "status": "ACTIVE", ...}

# 2. Drop matched images into the watched folders.
#    Demo-mode paths (auto-created by `make demo`):
cp tests/fixtures/images/cam18jdleofhtlhj6_L.jpg \
   ~/.tad/images/left/ABC12345678901234_L.jpg
cp tests/fixtures/images/cam18jdleofhtlhj6_R.jpg \
   ~/.tad/images/right/ABC12345678901234_R.jpg

# 3. Watch the dashboard -- the Production Details table updates live
#    via the SSE stream, the KPI cards refetch, and clicking a row
#    opens the Violation Detail page.

# 4. Stop the session when you're done
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
