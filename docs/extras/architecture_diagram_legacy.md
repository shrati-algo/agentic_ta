# Architecture Flow Diagrams

Detailed flow diagrams for the Trailing Arm Detection system, covering
both production wiring and the demo-mode infrastructure used for local
end-to-end testing.

Diagrams are written in [Mermaid](https://mermaid.js.org/) so they render
directly on GitHub, VS Code (with the Markdown Preview Mermaid Support
extension), or any modern Markdown viewer.

## Contents

1. [High-level system architecture](#1-high-level-system-architecture)
2. [Runtime processes and threads](#2-runtime-processes-and-threads)
3. [Session lifecycle (start -> stop)](#3-session-lifecycle)
4. [Per-image processing pipeline](#4-per-image-processing-pipeline)
5. [Measurement pipeline (classical CV)](#5-measurement-pipeline-classical-cv)
6. [Status classification decision tree](#6-status-classification-decision-tree)
7. [Chassis aggregation (dual-camera)](#7-chassis-aggregation)
8. [Real-time update path (SSE)](#8-real-time-update-path-sse)
9. [Demo-mode replay flow](#9-demo-mode-replay-flow)
10. [Frontend component tree](#10-frontend-component-tree)
11. [Data model (ER diagram)](#11-data-model-er-diagram)
12. [Deployment topology](#12-deployment-topology)

---

## 1. High-level system architecture

Shows every component and how they talk to each other. The three
coloured groups map to: **the browser**, **the backend service**, and
**persistence + filesystem**.

```mermaid
flowchart LR
    subgraph "Browser (localhost:5173 dev / :8000 prod)"
        UI_DB["Dashboard<br/>/home"]
        UI_VD["Violation Detail<br/>/home/details/:id"]
        SSE_CLIENT["EventSource<br/>(useLiveSession)"]
    end

    subgraph "TAD service (FastAPI, uvicorn :8000)"
        API["API Layer<br/>(routes_*)"]
        MW["RequestId<br/>Middleware"]
        ERR["Error envelope<br/>handler"]
        SM["Session Manager"]
        AGG["Aggregator<br/>(status matrix +<br/>asymmetry)"]
        BROKER["SSE Broker<br/>(per-session)"]
        CONS["Consumer loop<br/>(process_item)"]
        WATCH_L["Watcher L<br/>(watchdog)"]
        WATCH_R["Watcher R<br/>(watchdog)"]
        MEAS["Measurement<br/>pipeline<br/>(pure CV)"]
        REPO["Repositories<br/>+ Blob store"]
    end

    subgraph "Persistence"
        PG[(Postgres)]
        MINIO[(MinIO)]
        INMEM[["In-memory<br/>(demo mode)"]]
    end

    subgraph "Filesystem"
        LEFT_DIR[["/images/left/"]]
        RIGHT_DIR[["/images/right/"]]
        CAPTURE["Image capture<br/>(camera rigs)"]
    end

    UI_DB -- "HTTP /v1/*" --> API
    UI_VD -- "HTTP /v1/*" --> API
    SSE_CLIENT -- "SSE /v1/sessions/{id}/events" --> API

    API --> MW
    MW --> ERR
    API --> SM
    API --> REPO

    SM --> WATCH_L
    SM --> WATCH_R
    SM --> CONS
    SM --> AGG
    SM --> BROKER

    CAPTURE --> LEFT_DIR
    CAPTURE --> RIGHT_DIR
    LEFT_DIR -- "FS events" --> WATCH_L
    RIGHT_DIR -- "FS events" --> WATCH_R
    WATCH_L --> CONS
    WATCH_R --> CONS

    CONS --> MEAS
    CONS --> REPO
    CONS -- "camera_result" --> BROKER
    CONS --> AGG
    AGG --> REPO
    AGG -- "chassis_result" --> BROKER

    BROKER -- "SSE frames" --> SSE_CLIENT

    REPO -- "SqlRepos" --> PG
    REPO -- "MinIOStore" --> MINIO
    REPO -. "fakes (demo)" .-> INMEM

    style UI_DB fill:#dbeafe,stroke:#1e40af
    style UI_VD fill:#dbeafe,stroke:#1e40af
    style SSE_CLIENT fill:#dbeafe,stroke:#1e40af
    style PG fill:#fef3c7,stroke:#b45309
    style MINIO fill:#fef3c7,stroke:#b45309
    style INMEM fill:#fef3c7,stroke:#b45309
    style CAPTURE fill:#fef3c7,stroke:#b45309
    style LEFT_DIR fill:#fef3c7,stroke:#b45309
    style RIGHT_DIR fill:#fef3c7,stroke:#b45309
```

---

## 2. Runtime processes and threads

Where the work actually executes. Uvicorn is single-worker on purpose —
session state is in-memory and mustn't be sharded (see CLAUDE.md
"Never" list).

```mermaid
flowchart TB
    subgraph "Single Uvicorn process"
        subgraph "asyncio event loop"
            ROUTE["HTTP/SSE route handlers"]
            CONS_TASK["Consumer task<br/>(per session)"]
            REPLAY_TASK["Replay task<br/>(demo mode only)"]
            BROKER_STATE["SSE broker state"]
        end

        subgraph "watchdog threads"
            OBS_L["Observer L<br/>(ReadDirectoryChangesW)"]
            OBS_R["Observer R"]
        end

        subgraph "asyncio thread pool"
            CV["CV worker<br/>(cv2.* releases GIL)"]
        end

        QUEUE{{asyncio.Queue}}
        BLOB_T["MinIO client<br/>(wrapped in to_thread)"]
    end

    OBS_L -- "call_soon_threadsafe" --> QUEUE
    OBS_R -- "call_soon_threadsafe" --> QUEUE
    QUEUE --> CONS_TASK
    CONS_TASK -- "await asyncio.to_thread" --> CV
    CONS_TASK -- "await" --> BLOB_T
    CONS_TASK -- "await" --> BROKER_STATE
    REPLAY_TASK -. "bypasses queue<br/>drives consumer<br/>directly" .-> CV
    ROUTE --> BROKER_STATE

    style CV fill:#dcfce7,stroke:#15803d
    style QUEUE fill:#fef9c3,stroke:#a16207
```

---

## 3. Session lifecycle

End-to-end sequence for starting a session, processing an image pair,
and stopping.

```mermaid
sequenceDiagram
    autonumber
    participant FE as Frontend
    participant API as FastAPI routes
    participant SM as SessionManager
    participant REPO as SessionRepo
    participant BR as SseBroker
    participant WL as Watcher L
    participant WR as Watcher R
    participant CL as Consumer loop

    FE->>API: POST /v1/sessions/start<br/>{started_by, shift, area}
    API->>SM: start(...)
    SM->>SM: validate calibrations<br/>validate image dirs
    SM->>REPO: INSERT sessions row (ACTIVE)
    SM->>BR: create broker
    SM->>WL: start()
    SM->>WR: start()
    SM->>CL: create_task(consumer_loop)
    SM->>BR: publish session_opened
    SM-->>API: SessionRuntime
    API-->>FE: 201 StartResponse

    FE->>API: GET /v1/sessions/{id}/events (SSE)
    API->>BR: subscribe()
    BR-->>FE: event stream (open)

    Note over WL,CL: Image pair drops into<br/>/images/left and /images/right

    WL->>CL: enqueue QueueItem(L)
    WR->>CL: enqueue QueueItem(R)

    CL->>CL: process_item L<br/>(see diagram 4)
    CL-->>BR: publish camera_result L
    BR-->>FE: event camera_result L

    CL->>CL: process_item R
    CL-->>BR: publish camera_result R
    BR-->>FE: event camera_result R

    Note over CL,BR: Aggregator joins the pair

    CL->>BR: publish chassis_result
    BR-->>FE: event chassis_result

    FE->>API: POST /v1/sessions/{id}/stop
    API->>SM: stop(id)
    SM->>WL: stop()
    SM->>WR: stop()
    SM->>CL: set stop_event, await drain
    SM->>SM: aggregator.flush()<br/>(orphans -> REVIEW)
    SM->>REPO: UPDATE sessions SET status=STOPPED
    SM->>BR: publish session_closed
    SM->>BR: close()
    BR-->>FE: session_closed + disconnect
    SM-->>API: StopResponse{summary}
    API-->>FE: 200 StopResponse
```

---

## 4. Per-image processing pipeline

`process_item` in [`src/tad/sessions/consumer.py`](../src/tad/sessions/consumer.py).

```mermaid
flowchart TB
    START([Image appears in watched folder])
    DEDUP{Already seen?<br/>session_id + path + mtime}
    PARSE[parse_filename]
    BADNAME{{match regex?}}
    WAIT[wait_for_stable<br/>size-stability loop]
    READ[read bytes]
    VAL[validate_image<br/>resolution + blur + exposure]
    OK_VAL{ok?}
    CAL[lookup calibration<br/>for camera side]
    PIPE[measure_innermost_diameter<br/>asyncio.to_thread]
    ROW[build MeasurementRow]
    BLOB[put debug JPEG to blob store]
    INS[meas_repo.insert]
    CEVT[publish camera_result]
    AGG[aggregator.accept]

    WARN1[publish warning<br/>ERR_BAD_FILENAME]
    WARN2[publish warning<br/>ERR_IMAGE_QUALITY]

    START --> DEDUP
    DEDUP -- yes --> SKIP([return])
    DEDUP -- no --> PARSE
    PARSE --> BADNAME
    BADNAME -- no --> WARN1
    BADNAME -- yes --> WAIT
    WAIT --> READ
    READ --> VAL
    VAL --> OK_VAL
    OK_VAL -- no --> WARN2
    OK_VAL -- yes --> CAL
    CAL --> PIPE
    PIPE --> ROW
    ROW --> BLOB
    BLOB --> INS
    INS --> CEVT
    CEVT --> AGG
    AGG --> END([return])
    WARN1 --> END
    WARN2 --> END

    style WARN1 fill:#fee2e2,stroke:#dc2626
    style WARN2 fill:#fee2e2,stroke:#dc2626
    style PIPE fill:#dcfce7,stroke:#15803d
```

---

## 5. Measurement pipeline (classical CV)

`measure_innermost_diameter` in
[`src/tad/measurement/pipeline.py`](../src/tad/measurement/pipeline.py).
Algorithm version **`algo-1.3.0`** — see
[ADR-008](decisions/ADR-008.md) for the switch from Canny + RANSAC.

```mermaid
flowchart LR
    subgraph "Preprocessing"
        BGR([BGR image])
        GRAY[cvtColor -> gray]
        BLUR[GaussianBlur<br/>kernel=5]
    end

    subgraph "Isolation"
        TH[adaptiveThreshold<br/>GAUSSIAN_C, BINARY_INV<br/>block=51, c=10]
        MORPH[morph close<br/>3x3 kernel]
        CONT[findContours<br/>RETR_EXTERNAL]
        SORT[sort by area<br/>largest first]
        FILT[drop contours<br/>area &lt; 50]
    end

    subgraph "Detection (per contour)"
        MASK[mask grayscale<br/>by contour]
        HOUGH[HoughCircles<br/>minR = (target-tol)/2 * ppm<br/>maxR = (target+tol)/2 * ppm<br/>param2=20]
        FIRST{circle found?}
    end

    subgraph "Output"
        DIAM[diameter_mm<br/>= 2 * r_px * mm_per_px]
        EVAL[evaluate_status<br/>see diagram 6]
        CONF[compute_confidence<br/>linear in delta]
        ANNOT[render_debug_image]
        OUT([PipelineOutput])
    end

    ERR([ERR_NO_CIRCLE])

    BGR --> GRAY --> BLUR
    BLUR --> TH
    TH --> MORPH --> CONT --> SORT --> FILT
    FILT --> MASK
    MASK --> HOUGH --> FIRST
    FIRST -- no, try next contour --> MASK
    FIRST -- no contours left --> ERR
    FIRST -- yes --> DIAM
    DIAM --> EVAL
    DIAM --> CONF
    EVAL --> ANNOT
    CONF --> ANNOT
    ANNOT --> OUT

    style HOUGH fill:#ddd6fe,stroke:#5b21b6
    style ERR fill:#fee2e2,stroke:#dc2626
```

---

## 6. Status classification decision tree

`evaluate_status` in
[`src/tad/measurement/confidence.py`](../src/tad/measurement/confidence.py).

Band widths are configurable per `algo_params`. The current demo
configuration is shown in parentheses.

```mermaid
flowchart TD
    START([measured diameter_mm])
    IN_WINDOW{d in<br/>tolerance_min..max?<br/>(15..25 mm)}
    DELTA[delta = |d - target|<br/>(target = 20 mm)]
    D_OK{delta &lt;= ok_band?<br/>(1.0 mm)}
    D_SOK{delta &lt;= somewhat_ok?<br/>(1.5 mm)}

    PASS([PASS<br/>Okay<br/>green])
    REV([REVIEW<br/>Somewhat Okay<br/>amber])
    FAIL([FAIL<br/>Not Okay<br/>red])
    ERR([ERROR<br/>from pipeline<br/>grey])

    NO_CIRCLE([no circle<br/>detected])

    START --> HAS_CIRCLE{circle found?}
    HAS_CIRCLE -- no --> NO_CIRCLE --> ERR
    HAS_CIRCLE -- yes --> IN_WINDOW
    IN_WINDOW -- no --> FAIL
    IN_WINDOW -- yes --> DELTA --> D_OK
    D_OK -- yes --> PASS
    D_OK -- no --> D_SOK
    D_SOK -- yes --> REV
    D_SOK -- no --> FAIL

    style PASS fill:#dcfce7,stroke:#15803d,color:#14532d
    style REV fill:#fef3c7,stroke:#b45309,color:#713f12
    style FAIL fill:#fee2e2,stroke:#dc2626,color:#7f1d1d
    style ERR fill:#e5e7eb,stroke:#4b5563,color:#1f2937
```

---

## 7. Chassis aggregation

`Aggregator.accept` and the 4×4 status matrix in
[`src/tad/sessions/aggregator.py`](../src/tad/sessions/aggregator.py).

Per-camera results arrive in any order. When both sides of the same
chassis are present, emit a chassis_result and clear the pending entry.

```mermaid
stateDiagram-v2
    [*] --> Empty: session starts
    Empty --> WaitingR: accept(L)
    Empty --> WaitingL: accept(R)
    WaitingR --> Complete: accept(R)
    WaitingL --> Complete: accept(L)
    Complete --> [*]: emit chassis_result<br/>upsert chassis_record<br/>pop pending

    Empty --> FlushedOrphanL: flush() (session stop)<br/>no sides seen
    WaitingR --> FlushedOrphanR: flush()<br/>missing R
    WaitingL --> FlushedOrphanL: flush()<br/>missing L
    FlushedOrphanL --> [*]: emit chassis_result<br/>overall=REVIEW<br/>reason="missing side: L"
    FlushedOrphanR --> [*]: emit chassis_result<br/>overall=REVIEW<br/>reason="missing side: R"

    note right of Complete
        overall_status = combine_status(left, right)
        via 4x4 matrix (TRD 7.1).
        If both PASS but |L-R| > asymmetry_threshold_mm,
        downgrade to REVIEW.
    end note
```

Status matrix:

```
              RIGHT
           PASS   REVIEW   FAIL   ERROR
  L PASS   PASS   REVIEW   FAIL   ERROR
  E REVIEW REVIEW REVIEW   FAIL   ERROR
  F FAIL   FAIL   FAIL     FAIL   FAIL
  T ERROR  ERROR  ERROR    FAIL   ERROR
```

Plus the asymmetry rule: `PASS AND PASS with |L-R| > asymmetry_threshold_mm -> REVIEW`.

---

## 8. Real-time update path (SSE)

How a `chassis_result` event travels from the aggregator to the
Dashboard row that appears in the browser, with no page refresh.

```mermaid
sequenceDiagram
    participant AGG as Aggregator
    participant BR as SseBroker
    participant SUB as Subscriber queue
    participant ROUTE as SSE route handler
    participant ES as EventSource<br/>(browser)
    participant HOOK as useLiveSession
    participant PAGE as Dashboard

    AGG->>BR: publish(Event chassis_result, payload)
    BR->>SUB: put_nowait(event)
    Note over BR,SUB: Queue full?<br/>broker unsubscribe()<br/>(drop slow clients)

    loop stream
        ROUTE->>SUB: await queue.get()
        SUB-->>ROUTE: Event
        ROUTE-->>ES: event: chassis_result<br/>data: {...json...}
    end

    ES->>HOOK: addEventListener fires
    HOOK->>HOOK: setLastEvent({type, data, at})
    PAGE->>PAGE: useMemo(refreshKey) changes<br/>on chassis_result
    PAGE->>PAGE: re-run useChassisList<br/>re-run fetchSummary
    PAGE-->>ES: new row appears in the table<br/>KPI donut animates
```

---

## 9. Demo-mode replay flow

Local-host-only path that feeds chassis measurements from a fixture
folder on a timer. Entry point: the Dashboard mount in the browser.

See [`src/tad/api/routes_demo.py`](../src/tad/api/routes_demo.py) and
[`scripts/run_demo.py`](../scripts/run_demo.py).

```mermaid
sequenceDiagram
    participant FE as Dashboard<br/>(React)
    participant API as /v1/demo/*
    participant SM as SessionManager
    participant REPLAY as Replay task<br/>(asyncio)
    participant SRC as yca_valid<br/>source folder
    participant RUNTIME as SessionRuntime<br/>(meas_repo, broker,<br/>aggregator)

    Note over FE: Page mounts
    FE->>API: GET /v1/demo/replay/status
    API-->>FE: {running: false}

    FE->>API: POST /v1/demo/replay/start<br/>{interval_seconds: 20}
    API->>SM: start("demo-replay")
    SM-->>API: SessionRuntime
    API->>REPLAY: create_task(_replay_loop)
    API-->>FE: {running: true, total_pairs: 321}

    loop every 20 seconds
        REPLAY->>SRC: read next L + R file
        REPLAY->>REPLAY: chassis_no = DMAX + base32(index)
        REPLAY->>RUNTIME: write files into watched dirs
        REPLAY->>RUNTIME: _drive_one(L) [bypass watchdog]
        Note over RUNTIME: parse -> validate -> measure<br/>insert -> publish camera_result<br/>aggregator.accept
        REPLAY->>RUNTIME: _drive_one(R)
        Note over RUNTIME: pair complete -> publish chassis_result
        REPLAY->>REPLAY: _state.pairs_sent += 1
        REPLAY->>REPLAY: wait_for(stop_event, timeout=20s)
    end

    loop every 5s
        FE->>API: GET /v1/demo/replay/status
        API-->>FE: {running, pairs_sent, total_pairs}
        Note over FE: blue banner updates<br/>"N / 321 chassis sent"
    end

    Note over RUNTIME,FE: Chassis_result events still<br/>flow over SSE (diagram 8)<br/>so the KPI donut + table update
```

### Why the replay bypasses the folder watcher

On Windows, `watchdog.observers.Observer` (which wraps
`ReadDirectoryChangesW`) has a fixed event buffer. Under fast writes
the buffer can overflow and events are silently dropped — we observed
this empirically on the demo rig. The replay task keeps the filesystem
side-effect (so the /images/left and /images/right folders look
identical to production) but drives the consumer pipeline directly via
`_drive_one(rt, side, path)`. This guarantees every pair reaches the
aggregator regardless of watcher state.

---

## 10. Frontend component tree

React 18 + Vite + Tailwind + Recharts + TanStack Table. Component
responsibilities mirror the TRD Section 10 page breakdown.

```mermaid
flowchart TB
    APP["App<br/>(BrowserRouter + routes)"]

    subgraph "Pages"
        DASH["Dashboard<br/>/home"]
        VD["ViolationDetail<br/>/home/details/:id"]
    end

    subgraph "Dashboard components"
        HDR["Header<br/>nav + live indicator"]
        DONUT["KpiDonut<br/>Recharts PieChart"]
        TREND["KpiTrend<br/>Recharts LineChart"]
        ALERT["AlertsList"]
        FILT["FiltersBar<br/>date / shift / condition / search"]
        TBL["ProductionTable<br/>TanStack Table"]
        PAG["Pagination"]
    end

    subgraph "Detail components"
        CAM_L["CameraCard (L)<br/>debug img + decision buttons"]
        CAM_R["CameraCard (R)"]
        DETAIL_PANEL["DetailPanel<br/>KV list + Flag + Download"]
    end

    subgraph "Shared"
        PILL["StatusPill<br/>label + colour + icon"]
        LABELS["labels.ts<br/>(TRD 10.3 mapping)"]
    end

    subgraph "Hooks"
        LIVE["useLiveSession<br/>active session + SSE"]
        LIST["useChassisList<br/>paged fetch + refresh"]
    end

    subgraph "API clients"
        CL["api/client.ts<br/>axios instance"]
        DASH_API["api/dashboard.ts"]
        CH_API["api/chassis.ts"]
        SESS_API["api/sessions.ts"]
        SSE_API["api/sse.ts<br/>EventSource wrapper"]
        DEMO_API["api/demo.ts<br/>replay endpoints"]
    end

    APP --> DASH
    APP --> VD

    DASH --> HDR
    DASH --> DONUT
    DASH --> TREND
    DASH --> ALERT
    DASH --> FILT
    DASH --> TBL
    DASH --> PAG
    DASH --> LIVE
    DASH --> LIST
    DASH --> DEMO_API

    VD --> HDR
    VD --> CAM_L
    VD --> CAM_R
    VD --> DETAIL_PANEL
    VD --> CH_API

    TBL --> PILL
    ALERT --> PILL
    CAM_L --> PILL
    CAM_R --> PILL
    DETAIL_PANEL --> PILL
    PILL --> LABELS

    LIVE --> SESS_API
    LIVE --> SSE_API
    LIST --> CH_API
    DASH --> DASH_API

    CL -.-> DASH_API
    CL -.-> CH_API
    CL -.-> SESS_API
    CL -.-> DEMO_API

    style PILL fill:#e0e7ff,stroke:#4338ca
    style LABELS fill:#e0e7ff,stroke:#4338ca
```

---

## 11. Data model (ER diagram)

Persistence schema from
[`src/tad/persistence/migrations/versions/001_initial_schema.py`](../src/tad/persistence/migrations/versions/001_initial_schema.py).

```mermaid
erDiagram
    SESSIONS ||--o{ MEASUREMENTS : "produces"
    SESSIONS ||--o{ CHASSIS_RECORDS : "aggregates"
    MEASUREMENTS ||--o| CHASSIS_RECORDS : "left_measurement_id"
    MEASUREMENTS ||--o| CHASSIS_RECORDS : "right_measurement_id"

    SESSIONS {
        UUID session_id PK
        TIMESTAMPTZ started_at
        TIMESTAMPTZ stopped_at
        VARCHAR started_by
        VARCHAR status "ACTIVE | STOPPED | FAILED"
        TEXT left_dir
        TEXT right_dir
        VARCHAR algo_params_version
        VARCHAR shift
        VARCHAR area
        TEXT notes
        JSONB summary_json
    }

    MEASUREMENTS {
        UUID measurement_id PK
        UUID session_id FK
        VARCHAR chassis_no
        CHAR camera_side "L | R"
        TEXT image_path
        NUMERIC diameter_mm
        NUMERIC tolerance_min_mm
        NUMERIC tolerance_max_mm
        VARCHAR status "PASS | REVIEW | FAIL | ERROR"
        NUMERIC confidence_score
        INTEGER circle_center_x_px
        INTEGER circle_center_y_px
        NUMERIC radius_px
        NUMERIC mm_per_px
        VARCHAR calibration_version
        VARCHAR algo_params_version "pinned per row"
        TEXT debug_image_key
        VARCHAR error_code
        TEXT error_message
        TIMESTAMPTZ processed_at
        INTEGER latency_ms
    }

    CHASSIS_RECORDS {
        UUID chassis_record_id PK
        UUID session_id FK
        VARCHAR chassis_no
        UUID left_measurement_id FK
        UUID right_measurement_id FK
        NUMERIC left_diameter_mm
        NUMERIC right_diameter_mm
        NUMERIC avg_diameter_mm
        NUMERIC asymmetry_mm
        VARCHAR overall_status
        TEXT reason "missing side / asymmetry downgrade"
        VARCHAR operator_decision "CORRECT | INCORRECT"
        VARCHAR decided_by
        TIMESTAMPTZ decided_at
        BOOLEAN flagged
        VARCHAR shift
        VARCHAR area
        TIMESTAMPTZ aggregated_at
    }

    CALIBRATIONS {
        VARCHAR calibration_id PK
        CHAR camera_side "L | R"
        NUMERIC mm_per_px
        VARCHAR method
        TIMESTAMPTZ valid_from
        VARCHAR operator
        TEXT reference_image
        TIMESTAMPTZ imported_at
    }
```

Notes:
- Every measurement row pins `algo_params_version` + `calibration_version` so historical records are reproducible even after a version bump (traceability requirement US-08).
- `chassis_records` has `UNIQUE(session_id, chassis_no)` so the aggregator's upsert is idempotent.
- Calibrations live in YAML as the source of truth; this table is an audit mirror.

---

## 12. Deployment topology

Production (with Docker) vs demo mode (without).

```mermaid
flowchart LR
    subgraph PROD [Production plant server]
        TAD["tad-service container<br/>FastAPI + /dist static"]
        PG2[(postgres:16)]
        MINIO2[(minio)]
        LEFT2[["/plant/images/left<br/>(ro mount)"]]
        RIGHT2[["/plant/images/right<br/>(ro mount)"]]

        TAD -- "SQL via asyncpg" --> PG2
        TAD -- "S3 API" --> MINIO2
        LEFT2 --> TAD
        RIGHT2 --> TAD
    end

    subgraph DEMO [Local demo machine - no Docker]
        UV["uvicorn (run_demo.py)<br/>in-memory repos + blob"]
        VITE["Vite dev server :5173<br/>proxies /v1/* -> :8000"]
        LEFT3[["~/.tad/images/left"]]
        RIGHT3[["~/.tad/images/right"]]
        SRC3[["tests/fixtures/<br/>test_images/yca_valid"]]

        VITE --> UV
        LEFT3 --> UV
        RIGHT3 --> UV
        UV -- "replay copies pairs" --> LEFT3
        UV -- "replay copies pairs" --> RIGHT3
        SRC3 -- "replay source" --> UV
    end

    style TAD fill:#dbeafe,stroke:#1e40af
    style UV fill:#dbeafe,stroke:#1e40af
    style VITE fill:#dbeafe,stroke:#1e40af
    style PG2 fill:#fef3c7,stroke:#b45309
    style MINIO2 fill:#fef3c7,stroke:#b45309
```

Key differences:

| | Production | Demo |
|---|---|---|
| Command | `make up && make migrate && make serve` | `make demo` |
| Repositories | `SqlSessionRepository`, `SqlMeasurementRepository`, `SqlChassisRepository` | `InMemorySessionRepository` etc. |
| Blob store | `MinIOStore` | `InMemoryBlobStore` |
| Session lifetime | Shift (hours) | Browser session; data lost on Ctrl-C |
| Folder watchers | Real capture system writes JPEGs | Replay task writes from `yca_valid/` |
| Auth | `AUTH_ENABLED=true` + mTLS (future) | Off |
| `algo_params` | `configs/algo_params/algo-1.3.0.yaml` (target 47.25 mm) | Runtime overlay in `scripts/run_demo.py` (target 20 mm, wider bands) |

---

## References

- [TRD](trd_doc.txt) — normative requirements
- [PRD](prd_doc.txt) — product/user-story view
- [architecture.txt](architecture.txt) — the prose build guide (pair this diagram doc with it)
- [demo_walkthrough.md](demo_walkthrough.md) — step-by-step local-host test plan
- [ADR-001](decisions/ADR-001.md) — classical CV only, no ML
- [ADR-008](decisions/ADR-008.md) — switch to contour + masked Hough (algo-1.3.0)
- [ADR-009](decisions/ADR-009.md) — demo-mode infrastructure (this doc's diagram 9)
