# End-to-end demo on localhost

Boot the full TAD stack on your machine (backend + frontend) and exercise
every feature implemented through Phase 5.  No Docker required.

## Prerequisites

- **Python 3.11+** with the backend's dev deps installed
  (`pip install -e ".[dev]"` from the repo root, one time only).
- **Node.js 20+** with the frontend's deps installed
  (`cd frontend && npm install`, one time only).

You can verify both with:

```bash
python -c "import tad; print('backend OK')"
cd frontend && npm test && cd ..
```

## Three terminals, one browser

You'll run three things in parallel:

| Terminal | Command | What it does |
|----------|---------|---------------|
| 1 | `make demo`       | Backend on :8000 with in-memory storage |
| 2 | `make dev-ui`     | Vite dev server on :5173 with `/v1` proxy |
| 3 | `make demo-seed`  | Drops 5 synthetic chassis pairs |
| Browser | `http://localhost:5173/home` | The Dashboard |

## Step 1 — Start the backend (Terminal 1)

```bash
make demo
```

Expected output:

```
======================================================================
  TAD backend (DEMO MODE -- in-memory, no Docker required)
======================================================================
  Image folder  (left):  C:\Users\<you>\.tad\images\left
  Image folder  (right): C:\Users\<you>\.tad\images\right
  Calibration   (left):  ...cal-2026-03-14-L.yaml
  Calibration   (right): ...cal-2026-03-14-R.yaml
  Algo params:           algo-1.3.0
  API docs:              http://localhost:8000/docs
  Frontend (Vite):       http://localhost:5173/home
======================================================================
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Smoke test from another terminal (optional):

```bash
curl -s http://localhost:8000/v1/health     # -> {"status":"ok"}
curl -s http://localhost:8000/v1/ready      # -> {"status":"ready"}
```

Open <http://localhost:8000/docs> to see the OpenAPI UI — every route
shows up there with its schema.

## Step 2 — Start the frontend (Terminal 2)

```bash
make dev-ui
```

Expected output:

```
VITE v5.4.x  ready in 300 ms
  ➜  Local:   http://localhost:5173/
```

Open **<http://localhost:5173/home>** in your browser.  The dashboard
loads immediately but is empty — no chassis have been measured yet.
You'll see:

- Header with **Home** / Live View / Settings tabs
- **Violations Today** donut with 0% violation rate
- **Violation Trend** chart with no series yet
- **Recent Alerts** empty state
- Production Details table with *"Waiting for the first chassis."*

## Step 3 — Seed chassis measurements (Terminal 3)

```bash
make demo-seed
```

This:

1. Starts an active session via `POST /v1/sessions/start` (or reuses
   whichever one is active).
2. Generates 5 matched L/R synthetic image pairs with different
   diameters (19.93 mm, 20.91 mm, 16.47 mm, etc.).
3. Writes them into `~/.tad/images/{left,right}`.
4. Waits for the backend to measure each and checks `/v1/chassis`.

Expected output:

```
[seed] active session: <UUID>
[seed] dropping 5 matched L/R pairs...
       + HBUSRJGF4CBFPR9BN_L.jpg  +  HBUSRJGF4CBFPR9BN_R.jpg
       + ...
[seed] /v1/chassis total = 5
[seed] open http://localhost:5173/home and watch the rows appear.
```

**While the seed runs, watch the browser.**  You should see:

- Donut centre counter animates from 0.00% to ~60% (3 REVIEW / 5 total)
- Trend line now has a point for today
- Recent Alerts list fills with REVIEW/FAIL rows
- Production Details table prepends a row per chassis as it's processed
- Header shows a green dot + "Live" (SSE connected)

## Step 4 — Exercise the Violation Detail page

Click any row in the Production Details table.  The browser navigates
to `http://localhost:5173/home/details/<chassis_record_id>` and shows:

- Back button and "Violation Detail" title
- Two **CameraCard** panels (Cam1 / Cam2), each with:
  - The annotated debug image (from `/v1/debug/<measurement_id>`)
  - The status pill with the measured diameter in mm
  - **Correct Violation** / **Incorrect Violation** buttons
- **Detail Panel** on the right with:
  - Product ID, Overall Condition, Timestamp, Shift, Area
  - **Flag** toggle button
  - **Download** button (grabs the chassis record as a JSON file)

Try:

- Click **Correct Violation** on the left camera.  The button highlights;
  the backend records `operator_decision = CORRECT`.
- Click the **Flag** button.  The pill turns red and persists on refresh.
- Click **Download** — a `<chassis_no>.json` file saves.
- Click **← Back** — returns to the Dashboard.  If you re-open the
  same record, your decision + flag are still there.

## Step 5 — Verify the API from the command line

Every feature the UI exposes is also callable directly:

```bash
# List chassis (paginated)
curl -s http://localhost:8000/v1/chassis | python -m json.tool | head -30

# Dashboard summary
curl -s http://localhost:8000/v1/dashboard/summary | python -m json.tool

# Details for one chassis
curl -s "http://localhost:8000/v1/chassis/<chassis_record_id>" | python -m json.tool

# Debug image (JPEG bytes)
curl -s "http://localhost:8000/v1/debug/<measurement_id>" -o out.jpg

# Record a decision
curl -s -X POST "http://localhost:8000/v1/chassis/<chassis_record_id>/decision" \
     -H 'content-type: application/json' \
     -d '{"decision":"CORRECT","decided_by":"me"}'

# Toggle the flag
curl -s -X POST "http://localhost:8000/v1/chassis/<chassis_record_id>/flag" \
     -H 'content-type: application/json' \
     -d '{"flagged":true,"by":"me"}'
```

Watch the browser: the dashboard refreshes in real time when events
arrive over the SSE stream.

## Step 6 — Stop the session

From the browser you can't stop the session yet (Stop button is part of
the optional Phase 7 admin UI).  From a terminal:

```bash
# Find the active session
SID=$(curl -s "http://localhost:8000/v1/sessions?status=ACTIVE" | python -c "import sys,json; print(json.load(sys.stdin)[0]['session_id'])")
curl -s -X POST "http://localhost:8000/v1/sessions/$SID/stop" | python -m json.tool
```

Expected response:

```json
{
  "session_id": "...",
  "status": "STOPPED",
  "stopped_at": "2026-...",
  "summary": {
    "total": 5,
    "pass": 2,
    "review": 3,
    "fail": 0,
    "error": 0,
    "incomplete": 0
  }
}
```

The dashboard freezes its last snapshot (SSE closes), exactly as the
TRD specifies.

## Step 7 — Try the real trailing-arm fixtures

The demo algo_params are tuned to a 20 mm target, so the committed
real test images work too:

```bash
cp tests/fixtures/images/cam18jdleofhtlhj6_L.jpg \
   ~/.tad/images/left/REALFIXTURE000001_L.jpg
cp tests/fixtures/images/cam18jdleofhtlhj6_R.jpg \
   ~/.tad/images/right/REALFIXTURE000001_R.jpg
```

You should see a new row appear with a measured diameter in the
19.5-20.9 mm range.  The `/v1/debug/` image on the detail page shows the
detected circle on the actual industrial photo.

## Tear-down

- **Terminal 3**: already exits after seeding.
- **Terminal 2**: `Ctrl-C` stops Vite.
- **Terminal 1**: `Ctrl-C` stops the backend.  All in-memory data is lost
  (by design — the point of demo mode).  `~/.tad/images/` stays on disk;
  next `make demo` will pick it back up.

## What you've just tested

| Feature | Route | Phase |
|---------|-------|-------|
| Session start / stop | `POST /v1/sessions/start`, `/stop` | 4 |
| Active-session discovery | `GET /v1/sessions?status=ACTIVE` | 4 |
| Folder watcher | `watchdog` on `~/.tad/images/{L,R}/` | 4 |
| Filename parse + image validate + measure | consumer loop | 2-4 |
| Chassis aggregation + status matrix | `/v1/sessions/.../events` | 4 |
| SSE live updates | `GET /v1/sessions/{id}/events` | 4 |
| Measurement pipeline (algo-1.3.0) | — | 3 |
| Chassis list + filters | `GET /v1/chassis` | 4 |
| Chassis detail | `GET /v1/chassis/{id}` | 4 |
| Decision + flag | `POST /v1/chassis/{id}/decision`, `/flag` | 4 |
| Dashboard summary | `GET /v1/dashboard/summary` | 4 |
| Debug image streaming | `GET /v1/debug/{measurement_id}` | 4 |
| React Dashboard + live SSE | `/home` | 5 |
| React Violation Detail | `/home/details/:id` | 5 |

That's every P0 user story from `docs/user_stories.txt` (US-01, US-02,
US-03, US-04, US-05, US-06, US-07, US-08, US-09, US-10, US-18) plus
half the P1 stories (decision US-12, flag/note workflow).

## Troubleshooting

**"connection refused" from seed_demo.py** — The backend isn't running.
Check Terminal 1.  Is it still in the uvicorn loop?  Did you accidentally
`Ctrl-C` it?

**Dashboard says "Reconnecting..." forever** — The SSE connection to the
backend is broken.  Usually this means the backend restarted and the
browser's `EventSource` is still holding a stale handle.  Refresh the
page.

**Chassis never appears after seeding** — Look at Terminal 1's log for
`ERR_BAD_FILENAME` or `ERR_IMAGE_QUALITY` warnings.  The seed script
produces well-formed images, but if your machine has very limited RAM
the image generation can be slow — the script retries automatically.

**Port 8000 / 5173 already in use** — Another process is running.  Find
it with `netstat -ano | grep :8000` and kill it, or change the port in
`scripts/run_demo.py` / `frontend/vite.config.ts`.

**Windows + Git Bash: `make` not found** — Install GNU Make via
Chocolatey (`choco install make`) or just run the underlying commands
directly: `python scripts/run_demo.py`, `cd frontend && npm run dev`,
`python scripts/seed_demo.py`.
