# TAD API reference

HTTP reference for every route implemented through Phase 5. All paths
live under `/v1/`; breaking changes move to `/v2/` with a migration plan
(TRD Section 8).

Paired with:
- [`src/tad/api/schemas.py`](../src/tad/api/schemas.py) — the authoritative
  Pydantic models
- [`src/tad/api/routes_*.py`](../src/tad/api/) — the route implementations
- [`architecture_diagram.md`](architecture_diagram.md) — visual flow diagrams
- Swagger UI at **<http://localhost:8000/docs>** — interactive reference

## Conventions

- **Content-Type**: all request bodies are `application/json`.
- **Request ID**: every request gets an `X-Request-Id` header (echoed
  in the response). Non-2xx responses include it in the error envelope.
- **Error envelope** — every non-2xx response looks like:
  ```json
  {
    "error_code": "ERR_XXX",
    "error_message": "human-readable detail",
    "request_id": "rid-abcdef012345"
  }
  ```
- **Timestamps** — ISO 8601 UTC, e.g. `2026-04-17T05:27:43.990505Z`.
- **UUIDs** — client-side generated, canonical form `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`.

## Error codes

| Code | HTTP | Source |
|------|------|--------|
| `ERR_BAD_FILENAME`            | 400 | filename doesn't match the VIN regex |
| `ERR_IMAGE_QUALITY`           | 400 | validator rejected the image |
| `ERR_NO_CALIBRATION`          | 503 | missing / invalid calibration YAML |
| `ERR_SESSION_NOT_ACTIVE`      | 404 | no session with that ID is active |
| `ERR_SESSION_ALREADY_ACTIVE`  | 409 | a session is already running |
| `ERR_FOLDER_UNAVAILABLE`      | 503 | watched image folder isn't reachable |
| `ERR_NO_CIRCLE`               | 422 | pipeline couldn't detect a circle |
| `ERR_CHASSIS_NOT_FOUND`       | 404 | unknown chassis_record_id |
| `ERR_MEASUREMENT_NOT_FOUND`   | 404 | unknown measurement_id |
| `ERR_VALIDATION`              | 422 | Pydantic rejected the request body |
| `ERR_INTERNAL`                | 500 | uncaught exception (no stack trace sent) |

---

## Health / readiness

### `GET /v1/health`
Liveness probe — always 200 if the process is alive.

```bash
curl -s http://localhost:8000/v1/health
# {"status":"ok"}
```

### `GET /v1/ready`
Readiness probe — 200 only when all dependencies are healthy.

Checks:
- Both calibration YAML files load.
- Both image directories exist.
- The configured `algo_params_version` loads.
- Blob store responds to a probe.

```bash
curl -s http://localhost:8000/v1/ready
# {"status":"ready"}                                       # 200
# {"status":"not ready","errors":["left image dir ..."]}   # 503
```

---

## Sessions

### `POST /v1/sessions/start`
Begin a measurement session, spin up folder watchers, open the SSE
broker. Fails with `ERR_SESSION_ALREADY_ACTIVE` (409) if one is
running.

Request:
```json
{
  "started_by": "operator-42",
  "shift": "A",
  "area": "Welding",
  "notes": "line 1"
}
```

Response (201):
```json
{
  "session_id": "9b4e...",
  "status": "ACTIVE",
  "left_dir": "/images/left",
  "right_dir": "/images/right",
  "algo_params_version": "algo-1.3.0",
  "left_calibration": "cal-2026-03-14-L",
  "right_calibration": "cal-2026-03-14-R",
  "started_at": "2026-04-17T09:10:00Z"
}
```

```bash
curl -s -X POST http://localhost:8000/v1/sessions/start \
     -H 'content-type: application/json' \
     -d '{"started_by":"me","shift":"A","area":"Welding"}'
```

### `POST /v1/sessions/{session_id}/stop`
Stop watchers, drain in-flight items, flush orphan chassis as `REVIEW`,
close the broker.

Response (200):
```json
{
  "session_id": "9b4e...",
  "status": "STOPPED",
  "stopped_at": "2026-04-17T10:25:00Z",
  "summary": {
    "total": 27,
    "pass": 6,
    "review": 6,
    "fail": 15,
    "error": 0,
    "incomplete": 0
  }
}
```

### `GET /v1/sessions?status=ACTIVE`
List sessions filtered by status. The frontend uses this on Dashboard
mount to discover the current session.

```bash
curl -s "http://localhost:8000/v1/sessions?status=ACTIVE"
# [{"session_id": "...", "status": "ACTIVE", "started_at": "...", ...}]
```

### `GET /v1/sessions/{session_id}/events`
Server-Sent Events stream for the session. Emits:

| Event type | Payload fields |
|------------|----------------|
| `session_opened` | session_id, started_at, algo_params_version, left_calibration, right_calibration |
| `camera_result` | measurement_id, chassis_no, camera_side, diameter_mm, status, confidence_score, processed_at, debug_image_url |
| `chassis_result` | chassis_record_id, chassis_no, left/right_diameter_mm, avg_diameter_mm, asymmetry_mm, overall_status, shift, area, aggregated_at |
| `warning` | chassis_no, file, error_code, message |
| `session_closed` | session_id, stopped_at, summary |

```bash
curl -N http://localhost:8000/v1/sessions/<SID>/events
# event: camera_result
# data: {"measurement_id":"...","chassis_no":"...","camera_side":"L",...}
```

Slow clients are dropped from the broker rather than back-pressuring the producer (see
[architecture_diagram.md §8](architecture_diagram.md#8-real-time-update-path-sse)).

### `GET /v1/sessions/{session_id}/results?since=<iso>`
Polling fallback for clients that can't hold an SSE connection. Returns
every measurement row for the session, optionally filtered by
`processed_at >= since`.

---

## Chassis

### `GET /v1/chassis`
Paginated chassis list — drives the Dashboard table.

Query parameters:

| Name | Default | Notes |
|------|---------|-------|
| `from` | — | ISO 8601 lower bound on `aggregated_at` |
| `to` | — | ISO 8601 upper bound |
| `status` | — | `PASS` / `REVIEW` / `FAIL` / `ERROR` |
| `shift` | — | `A` / `B` / `C` |
| `search` | — | chassis_no prefix |
| `page` | `1` | |
| `page_size` | `10` | |

```bash
curl -s "http://localhost:8000/v1/chassis?status=REVIEW&page=1&page_size=10"
```

Response:
```json
{
  "page": 1,
  "page_size": 10,
  "total": 87,
  "items": [
    {
      "chassis_record_id": "...",
      "chassis_no": "DMAX..........A",
      "overall_status": "REVIEW",
      "avg_diameter_mm": 20.578,
      "timestamp": "2026-04-17T06:36:42Z",
      "shift": "A",
      "area": "Welding",
      "flagged": false
    }
  ]
}
```

### `GET /v1/chassis/{chassis_record_id}`
Full chassis record with both per-camera measurements — drives the
Violation Detail page.

```bash
curl -s "http://localhost:8000/v1/chassis/<id>"
```

```json
{
  "chassis_record_id": "...",
  "chassis_no": "DMAX..........A",
  "overall_status": "REVIEW",
  "flagged": false,
  "timestamp": "2026-04-17T06:36:42Z",
  "shift": "A",
  "area": "Welding",
  "left":  {"measurement_id":"...","diameter_mm":18.40,"status":"REVIEW","confidence":0.59,"debug_image_url":"/v1/debug/..."},
  "right": {"measurement_id":"...","diameter_mm":21.78,"status":"REVIEW","confidence":0.42,"debug_image_url":"/v1/debug/..."},
  "operator_decision": null
}
```

### `POST /v1/chassis/{id}/decision`
Record the operator's CORRECT / INCORRECT decision on a REVIEW chassis.
Returns the updated record.

```json
{"decision": "CORRECT", "decided_by": "operator-42"}
```

```bash
curl -s -X POST "http://localhost:8000/v1/chassis/<id>/decision" \
     -H 'content-type: application/json' \
     -d '{"decision":"CORRECT","decided_by":"me"}'
```

### `POST /v1/chassis/{id}/flag`
Toggle the flagged state. Returns the updated record.

```json
{"flagged": true, "by": "operator-42"}
```

---

## Measurements

### `GET /v1/measurements/{measurement_id}`
Single measurement row, including the linked `debug_image_url`,
`algo_params_version`, `calibration_version` (traceability fields).

### `GET /v1/debug/{measurement_id}`
Streams the annotated debug JPEG from blob storage. Response headers
include `content-type: image/jpeg`. The frontend uses this URL directly
in the `<img>` tag on the Violation Detail page.

---

## Dashboard summary

### `GET /v1/dashboard/summary?from=<iso>&to=<iso>`
KPI snapshot for the Dashboard header cards.

```bash
curl -s http://localhost:8000/v1/dashboard/summary | python -m json.tool
```

```json
{
  "total": 27,
  "pass": 6,
  "review": 6,
  "fail": 15,
  "violation_pct": 77.78,
  "trend": [
    {"date": "2026-04-17", "review": 6, "fail": 15}
  ],
  "recent_alerts": [
    {
      "chassis_record_id": "...",
      "chassis_no": "DMAX..........A",
      "timestamp": "2026-04-17T06:36:48Z",
      "overall_status": "REVIEW"
    }
  ]
}
```

---

## Demo-only (not part of the production API)

These endpoints live under `/v1/demo/*` and drive local-host
demonstrations. Do **not** call them against a plant deployment
(see [ADR-009](decisions/ADR-009.md)).

### `POST /v1/demo/replay/start`
Begin copying paired L/R images from a source folder into the watched
folders at an interval. Starts a session if none is active.

```json
{
  "source_dir": "tests/fixtures/test_images/yca_valid",
  "interval_seconds": 20,
  "max_pairs": 321
}
```

All fields optional; `source_dir` defaults to the committed
`yca_valid` fixtures.

Response:
```json
{
  "running": true,
  "source_dir": "...",
  "interval_seconds": 20.0,
  "pairs_sent": 0,
  "total_pairs": 321
}
```

### `POST /v1/demo/replay/stop`
Cancel the replay task. Idempotent.

### `GET /v1/demo/replay/status`
Current replay state (the Dashboard polls this every 5s to update the
blue banner).

---

## End-to-end example

```bash
# 1. Start a session
SID=$(curl -s -X POST http://localhost:8000/v1/sessions/start \
     -H 'content-type: application/json' \
     -d '{"started_by":"demo","shift":"A","area":"Welding"}' \
     | python -c "import sys,json;print(json.load(sys.stdin)['session_id'])")

# 2. Subscribe to the event stream (in another terminal)
curl -N http://localhost:8000/v1/sessions/$SID/events

# 3. Drop a matched pair (demo folders auto-created by `make demo`)
cp tests/fixtures/images/cam18jdleofhtlhj6_L.jpg ~/.tad/images/left/MALBB51BLPM123456_L.jpg
cp tests/fixtures/images/cam18jdleofhtlhj6_R.jpg ~/.tad/images/right/MALBB51BLPM123456_R.jpg

# ... watch camera_result + chassis_result events stream ...

# 4. Fetch the result
curl -s "http://localhost:8000/v1/chassis?search=MALBB51" | python -m json.tool

# 5. Record a decision on the chassis
CRID=$(curl -s "http://localhost:8000/v1/chassis?search=MALBB51" \
       | python -c "import sys,json;print(json.load(sys.stdin)['items'][0]['chassis_record_id'])")
curl -s -X POST "http://localhost:8000/v1/chassis/$CRID/decision" \
     -H 'content-type: application/json' \
     -d '{"decision":"CORRECT","decided_by":"demo"}'

# 6. Stop the session
curl -s -X POST "http://localhost:8000/v1/sessions/$SID/stop" | python -m json.tool
```
