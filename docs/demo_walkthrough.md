# End-to-end demo on localhost

Boot the full TAD stack on your machine (backend + frontend) and watch
it exercise every feature built through Phase 5 with real industrial
images — no Docker required.

## Prerequisites (one-time)

- **Python 3.11+** with the backend's dev deps installed
  (`pip install -e ".[dev]"` from the repo root).
- **Node.js 20+** with the frontend's deps installed
  (`cd frontend && npm install`).

Verify:

```bash
python -c "import tad; print('backend OK')"
cd frontend && npm test && cd ..
```

You should see the Python import succeed and 27 Vitest tests pass.

---

## Two terminals, one browser

The recommended path — zero config, the replay starts itself when you
open the Dashboard.

| Terminal | Command | What it does |
|----------|---------|---------------|
| 1 | `make demo`   | Backend on :8000 with in-memory storage; auto-creates `~/.tad/images/{left,right}`; relaxed `algo-1.3.0` bands for a demo-friendly PASS/REVIEW/FAIL mix |
| 2 | `make dev-ui` | Vite dev server on :5173 with `/v1` proxy to the backend |
| Browser | <http://localhost:5173/home> | Dashboard — calls `/v1/demo/replay/start` on mount |

Once you open the browser:

- Dashboard header shows a small green dot + **"Live"** (SSE connected).
- A blue banner at the top reads
  *"Demo replay: streaming — N / 321 chassis sent at 20s intervals"*.
- Every 20 seconds a new row prepends to the Production Details table.
- KPI donut, Violation Trend line, and Recent Alerts all animate as
  events land.

> The diagrams in [architecture_diagram.md §9 (Demo-mode replay flow)](architecture_diagram.md#9-demo-mode-replay-flow)
> show the sequence end-to-end.

---

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

Smoke test from another terminal:

```bash
curl -s http://localhost:8000/v1/health     # -> {"status":"ok"}
curl -s http://localhost:8000/v1/ready      # -> {"status":"ready"}
```

<http://localhost:8000/docs> shows the OpenAPI Swagger UI for every
route.

## Step 2 — Start the frontend (Terminal 2)

```bash
make dev-ui
```

Expected output:

```
VITE v5.4.x  ready in 300 ms
  ➜  Local:   http://localhost:5173/
```

Open **<http://localhost:5173/home>** in your browser. The Dashboard
loads and **automatically** calls `POST /v1/demo/replay/start` with a
20-second interval — no Terminal 3 required.

Initial view (before the first pair lands):

- Header with `algo8 MARUTI` logo, **Home** / Live View / Settings tabs.
- Violations Today donut at 0.00%.
- Violation Trend chart empty.
- Recent Alerts empty.
- Production Details table says *"Waiting for the first chassis."*.
- Blue banner: *"Demo replay: streaming — 0 / 321 chassis sent at 20s intervals"*.

Within a few seconds the first pair processes and the dashboard starts
filling up.

---

## Step 3 — Observe the live flow

As the replay runs you'll see three kinds of chassis rows appear. They
correspond to the three status bands described in
[architecture_diagram.md §6](architecture_diagram.md#6-status-classification-decision-tree).

### Demo band configuration

`scripts/run_demo.py` overlays these values on top of the committed
`algo-1.3.0`:

| Parameter | Value | Meaning |
|-----------|------:|---------|
| `target.diameter_mm` | 20.0 | Expected diameter on the yca_valid fixtures |
| `target.radius_tolerance_mm` | 2.0 | Hough radius search window |
| `tolerance.min_mm` / `max_mm` | 15.0 / 25.0 | Absolute FAIL window |
| `tolerance.ok_band_mm` | **1.0** | PASS when per-camera `|d - 20| <= 1.0` |
| `tolerance.somewhat_ok_band_mm` | **1.5** | REVIEW when `1.0 < |d - 20| <= 1.5` |
| `tolerance.asymmetry_threshold_mm` | **2.5** | PASS→REVIEW when `|left - right| > 2.5` |

So the dashboard displays:

- 🟢 **Okay (PASS)** — both L and R within ±1.0 mm of 20 mm, and
  |L-R| ≤ 2.5 mm.
- 🟡 **Somewhat Okay (REVIEW)** — one or both sides drift 1.0-1.5 mm
  from target, or the pair would have been PASS but the L/R asymmetry
  exceeded 2.5 mm.
- 🔴 **Not Okay (FAIL)** — a side is > 1.5 mm from target, or the
  average is outside [15, 25] mm.

A typical 30-chassis sample from `yca_valid/` yields roughly
**6 PASS / 6 REVIEW / 15 FAIL** (demo measurements sit right on the
band boundaries, which is what makes a good mix in the UI).

> The committed `configs/algo_params/algo-1.3.0.yaml` still pins the
> production target (47.25 mm). Only the demo entry point loosens
> these thresholds.

---

## Step 4 — Click into the Violation Detail page

Click any row in the Production Details table.

The browser navigates to `/home/details/<chassis_record_id>` and shows:

- **← Back** button and "Violation Detail" heading.
- Two **CameraCard** panels (Cam1 / Cam2), each with:
  - The annotated debug JPEG (green circle on the real industrial
    trailing-arm photo from `yca_valid/`).
  - Status pill and measured diameter in mm.
  - **Incorrect Violation** and **Correct Violation** buttons.
- **Detail Panel** on the right: Product ID, Overall Condition,
  Timestamp, Shift, Area, **Flag** button, **Download** button.

Try:

- Click **Correct Violation** on the Cam1 card — button highlights;
  POSTs to `/v1/chassis/{id}/decision`.
- Click **Flag** — pill turns red, POSTs to `/v1/chassis/{id}/flag`.
- Click **Download** — saves `<chassis_no>.json` with the full record.
- Click **← Back** — returns to the Dashboard with your changes
  reflected (the row now shows a red flag icon).

---

## Step 5 — Drive the API by hand (optional)

Every feature the UI exposes is callable directly:

```bash
# Replay control
curl -s http://localhost:8000/v1/demo/replay/status | python -m json.tool
curl -s -X POST http://localhost:8000/v1/demo/replay/stop | python -m json.tool

# Or start with a custom interval / pair count
curl -s -X POST http://localhost:8000/v1/demo/replay/start \
     -H 'content-type: application/json' \
     -d '{"interval_seconds": 2, "max_pairs": 10}'

# Paginated chassis list
curl -s "http://localhost:8000/v1/chassis?page=1&page_size=10" | python -m json.tool | head -30

# One chassis detail
curl -s "http://localhost:8000/v1/chassis/<id>" | python -m json.tool

# Debug image bytes
curl -s "http://localhost:8000/v1/debug/<measurement_id>" -o out.jpg

# Dashboard summary
curl -s http://localhost:8000/v1/dashboard/summary | python -m json.tool
```

---

## Step 6 — Stop the session

From the browser you can't stop the session (the Stop button is part
of the optional Phase 7 admin UI). From a terminal:

```bash
SID=$(curl -s "http://localhost:8000/v1/sessions?status=ACTIVE" \
      | python -c "import sys,json; print(json.load(sys.stdin)[0]['session_id'])")
curl -s -X POST "http://localhost:8000/v1/sessions/$SID/stop" | python -m json.tool
```

Returns the shift summary:

```json
{
  "session_id": "...",
  "status": "STOPPED",
  "stopped_at": "2026-...",
  "summary": {
    "total": 27, "pass": 6, "review": 6, "fail": 15,
    "error": 0, "incomplete": 0
  }
}
```

The dashboard freezes its last snapshot (SSE closes cleanly). Refresh
to start a new session + replay.

---

## Alternative path — synthetic seed instead of real images

If you just want to see the UI fill with chassis quickly and don't need
the real trailing-arm photos:

```bash
# In a third terminal, with `make demo` running:
make demo-seed     # 5 synthetic matched pairs, instant
# or:
python scripts/seed_demo.py 30
```

See [PLAN.md](../PLAN.md) for the synthetic seed details. This is the
reliable happy path for CI and throwaway smoke tests.

---

## Tear-down

- **Terminal 2** (Vite): `Ctrl-C`.
- **Terminal 1** (backend): `Ctrl-C`. In-memory data gone (by design).
- `~/.tad/images/` stays on disk; delete it with `rm -rf ~/.tad` for
  a fully fresh start.

---

## What this exercises

Every P0 user story from `docs/user_stories.txt` plus P1 decision +
flag flows. See the traceability table at the end of
[architecture_diagram.md §12 (Deployment topology)](architecture_diagram.md#12-deployment-topology)
for the feature → route → phase mapping.

---

## Troubleshooting

**Connection refused on :8000** — The backend isn't running. Check
Terminal 1. Did `make demo` exit? Port conflict? `netstat -ano | grep :8000`.

**Dashboard says "Reconnecting..." forever** — SSE handle gone stale
(usually after a backend restart). Refresh the page.

**Blue banner never appears** — the frontend couldn't reach
`/v1/demo/replay/start`. Most likely the Vite proxy isn't seeing the
backend; try <http://localhost:5173/v1/health> directly to confirm
the proxy works.

**Chassis stuck in all one colour** — the band overlay in
`scripts/run_demo.py` is loaded only at backend startup. If you edit
the bands, `Ctrl-C` the backend and `make demo` again.

**Port 5173 or 8000 in use** — kill the stale process:
`taskkill /F /IM python.exe` or `taskkill /F /IM node.exe` on Windows,
`lsof -ti:8000 | xargs kill` on macOS/Linux.

**Windows: "make not found"** — install GNU Make via Chocolatey
(`choco install make`) or just call the underlying commands:

```bash
python scripts/run_demo.py          # equivalent to `make demo`
cd frontend && npm run dev          # equivalent to `make dev-ui`
python scripts/seed_demo.py 5       # equivalent to `make demo-seed`
```

**Replay says "0 / 0 chassis"** — the source folder at
`tests/fixtures/test_images/yca_valid` is empty or not present. Drop
paired `*_L.jpg` / `*_R.jpg` files there, or supply a different
`source_dir` on the `/v1/demo/replay/start` request body.
