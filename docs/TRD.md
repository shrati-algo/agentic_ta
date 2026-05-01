# Technical Requirements Document — Trailing Arm Detection

================================================================================
                                                                                
                  TECHNICAL REQUIREMENTS DOCUMENT (TRD)                         
                                                                                
                        TRAILING ARM DETECTION                                  
          Automated Defect Detection in Assembly Line Production                
                                                                                
================================================================================

  DOMAIN        :  Computer Vision / Manufacturing Quality Inspection
  PROJECT TYPE  :  Vision-based Dimensional Measurement (classical CV only)
  VERSION       :  2.1  (Draft)
  SUPERSEDES    :  TRD v2.0 (frontend architecture added)
  PHASE         :  Phase 02 — Design (Technical Requirements & Architecture)
  PREDECESSOR   :  Use Case Document — Trailing Arm Detection (UC-TAD-001)
  OWNERS        :  Data Science Team (algorithm), Frontend Team (UI + API),
                   Assembly Line Operations (end users)

  WHAT CHANGED FROM v2.0
  ----------------------
     - Added Section 10: Frontend Application Architecture. Specifies
       the two-page UI (Dashboard + Violation Detail), the component
       breakdown visible in the approved mockups, the exact tool stack
       (React + Vite + Tailwind + Recharts + React Router), and the
       integration contract between frontend and backend.
     - Renumbered sections 10-26 from v2.0 to 11-27 to make room.
     - Section 9 (Real-Time Logging) now explicitly references the
       Frontend Application Architecture for rendering behaviour.
     - Added an ADR-007 for the frontend stack choice.


  HIGH-LEVEL FLOW
  ---------------

     Frontend calls Start API
            |
            v
     Service begins monitoring the configured folders for the
     LEFT camera and the RIGHT camera
            |
            v
     For each image that appears:
         1. parse chassis number from the filename
         2. run classical circle detection
         3. estimate the innermost circle diameter
         4. log the per-camera result in real time
            |
            v
     When BOTH left and right images of the same chassis have been
     processed, emit an OVERALL result for that chassis to the
     frontend log; the Dashboard's table and widgets update live

================================================================================


+------------------------------------------------------------------------------+
|                            TABLE OF CONTENTS                                 |
+------------------------------------------------------------------------------+

   1.  Purpose and Scope of This Document
   2.  Architecture Overview
   3.  Processing Flow (End-to-End)
   4.  Filename and Folder Conventions
   5.  Data Schema Contracts
   6.  Measurement Algorithm Design
   7.  Dual-Camera Result Aggregation
   8.  API Specification
   9.  Real-Time Logging to the Frontend
  10.  Frontend Application Architecture                           (NEW)
  11.  Algorithm Parameters and Calibration Versioning
  12.  Project Structure and Scaffolding
  13.  CLAUDE.md — Project Memory File
  14.  Architecture Decision Records (ADRs)
  15.  Infrastructure Requirements
  16.  Performance and SLA Requirements
  17.  Security, Privacy and Compliance
  18.  Testing and Validation Strategy
  19.  Deployment and Rollout Strategy
  20.  Monitoring, Drift Detection and Recalibration
  21.  Dependencies and External Systems
  22.  Technical Risks and Mitigation
  23.  Timeline and Milestones
  24.  Glossary
  25.  Appendix A — Example API Payloads
  26.  Appendix B — CLAUDE.md Template
  27.  Appendix C — ADR Template



================================================================================
  1. PURPOSE AND SCOPE OF THIS DOCUMENT
================================================================================

  This Technical Requirements Document (TRD) translates the approved Use
  Case Brief (UC-TAD-001) into a buildable engineering specification. It
  is the contract between:

      - Data Scientists              (own the measurement algorithm and
                                      its accuracy)
      - Frontend Developers          (own the Start/Stop API, the image
                                      folders, and the UI)
      - Assembly Line Operations     (consume the per-camera and overall
                                      measurement output)
      - Quality Assurance            (validate against manual caliper
                                      measurement)

  The solution is deliberately simple:

      - No deep-learning model is used. No YOLO, no ROI detector, no GPU,
        no training pipeline.
      - The approach is fully classical computer vision: pre-processing,
        edge detection, Hough circle detection, and RANSAC sub-pixel
        refinement.
      - The system is session-based: the frontend calls a Start API,
        the service begins processing images from the left-camera and
        right-camera folders, and results are streamed to the frontend
        log in real time.
      - The frontend is a two-page React app: a Dashboard and a
        Violation Detail page. Simple tooling throughout.

  IN SCOPE OF THIS TRD
  --------------------
    - Session-based Start/Stop API.
    - Folder monitoring for the left-camera and right-camera image
      directories.
    - Parsing of the chassis number from the image filename.
    - Classical measurement of the innermost circle diameter per image.
    - Per-camera logging and per-chassis (overall) aggregate logging.
    - Result persistence and audit trail.
    - Frontend application (Dashboard + Violation Detail pages).

  OUT OF SCOPE OF THIS TRD
  ------------------------
    - Any machine learning model.
    - Camera hardware selection and physical mounting (owned by Plant
      Engineering).
    - Defect measurements on components other than the trailing arm's
      innermost circle (future work, separate TRD required).
    - Downstream MES / ERP integration beyond persisting measurement
      records.



================================================================================
  2. ARCHITECTURE OVERVIEW
================================================================================

  The system is a long-running service that is driven by a session
  lifecycle. The frontend starts a session; the service then watches two
  configured folders (left camera, right camera) for new images. For every
  image that appears, the chassis number is parsed from the filename and
  a classical CV measurement pipeline runs. Per-camera results are
  emitted immediately; once both sides of the same chassis are processed,
  an overall aggregate result is emitted. The frontend renders these
  events on a live Dashboard; individual chassis can be drilled into
  on a Violation Detail page.

  KEY ARCHITECTURAL PROPERTIES
  ----------------------------
    - Serving mode       :  Session-based long-running service;
                            Start/Stop API; result streaming to frontend
    - Deployment target  :  On-premises, co-located with the assembly line
    - Measurement style  :  Classical CV only (deterministic, explainable)
    - Processing model   :  Per-image pipeline, with dual-camera aggregation
                            keyed by chassis number
    - Failure mode       :  Fail-safe — flag for manual inspection, never
                            silently pass a defective part
    - Output units       :  Millimetres (sub-pixel accuracy via RANSAC)
    - Frontend           :  Two-page React SPA (Dashboard, Violation
                            Detail) — see Section 10

  NO MACHINE LEARNING
  -------------------
    The measurement pipeline contains zero learned components. All
    behaviour is defined by a fixed set of algorithm parameters (stored
    as a versioned config) and a per-camera calibration (mm-per-pixel).
    This choice delivers:

      - determinism      — same input, same output, every time
      - explainability   — every step is inspectable and auditable
      - low ops burden   — no GPU, no model retraining, no drift-from-
                           weights
      - faster delivery  — no annotation, no training, no model registry



================================================================================
  3. PROCESSING FLOW (END-TO-END)
================================================================================


  +----------------------------------------------------------------------+
  |                       END-TO-END DATA FLOW                           |
  +----------------------------------------------------------------------+

   [Frontend UI]
        |
        |  POST /v1/sessions/start
        v
   +----------------+
   |   CV Service   |
   |   (FastAPI)    |
   +----------------+
        |
        |  session opened; begin monitoring
        v
   +---------------------------------------------+
   |  Folder Watchers                            |
   |                                             |
   |   /images/left/   <-- left-camera images    |
   |   /images/right/  <-- right-camera images   |
   +---------------------------------------------+
        |
        |  new image detected
        v
   +--------------------+      +-----------------------------+
   |  Filename Parser   | ---> | chassis_no, camera_side     |
   +--------------------+      +-----------------------------+
        |
        v
   +--------------------+
   | Image Validator    |   (resolution, blur, exposure, integrity)
   +--------------------+
        |
        v
   +--------------------------------------+
   |        Measurement Pipeline          |
   |  (grayscale -> CLAHE -> blur -> Canny|
   |   -> HoughCircles -> innermost pick  |
   |   -> RANSAC refinement -> mm convert)|
   +--------------------------------------+
        |
        v
   +------------------------+
   |  Per-Camera Result     |  -- streamed to frontend (cam1 OR cam2)
   |  (chassis, camera,     |
   |   diameter, status)    |
   +------------------------+
        |
        v
   +-------------------------------+
   |  Chassis Aggregator           |   wait until both L and R are done
   |  (keyed by chassis_no)        |   for this chassis_no
   +-------------------------------+
        |
        v
   +------------------------+
   |  Overall Result        |  -- streamed to frontend (chassis summary)
   |  (left, right, overall |
   |   status, asymmetry)   |      and appended to the dashboard table
   +------------------------+
        |
        v
   +--------------------+
   |  Persistence       |  Postgres (records) + blob storage (debug img)
   +--------------------+


  PIPELINE STAGES AND OWNERSHIP
  -----------------------------

    STAGE 1 | Session Start
      owner     : Frontend (caller) + CV Service (handler)
      action    : create session record; activate folder watchers

    STAGE 2 | Folder Monitoring
      owner     : CV Service
      action    : detect new files in /images/left/ and /images/right/;
                  enqueue them in arrival order per folder
      failure   : on missing/unreachable folder, abort session and return
                  ERR_FOLDER_UNAVAILABLE via the events stream

    STAGE 3 | Filename Parsing
      owner     : CV Service
      action    : extract chassis_no and camera_side from the filename
                  using the convention in Section 4
      failure   : ERR_BAD_FILENAME — the file is skipped and logged

    STAGE 4 | Image Validation
      owner     : CV Service
      checks    : resolution, Laplacian blur variance >= 100, exposure
                  mean in acceptable band, JPEG/PNG integrity
      failure   : ERR_IMAGE_QUALITY — the image is skipped and logged

    STAGE 5 | Measurement
      owner     : Data Science Team (algorithm)
      input     : validated image + camera-specific calibration
      output    : diameter_mm, confidence, circle geometry,
                  annotated debug image
      failure   : ERR_NO_CIRCLE when no valid circle is detected

    STAGE 6 | Per-Camera Emit
      owner     : CV Service
      action    : persist the per-camera record and push a
                  "camera_result" event to the session event stream

    STAGE 7 | Chassis Aggregation
      owner     : CV Service
      action    : when both left and right per-camera records exist for
                  the same chassis_no within the same session, compute
                  the overall status (see Section 7) and push a
                  "chassis_result" event

    STAGE 8 | Session Stop
      owner     : Frontend (caller) + CV Service (handler)
      action    : on POST /stop, deactivate watchers, flush any pending
                  aggregations, close the event stream



================================================================================
  4. FILENAME AND FOLDER CONVENTIONS
================================================================================

  The chassis number is the primary key for every measurement. Because
  it is parsed from the filename, the filename convention is a CONTRACT
  with Plant Engineering and the Frontend team.


  4.1  FOLDER LAYOUT
  ------------------

      /images/
          left/                <-- LEFT camera (Cam1) writes here
              <chassis_no>_L.jpg
              ...
          right/               <-- RIGHT camera (Cam2) writes here
              <chassis_no>_R.jpg
              ...

      Folder paths are configurable via environment variables
      (IMAGES_LEFT_DIR, IMAGES_RIGHT_DIR). The folders must exist and
      be readable before POST /sessions/start returns 200.


  4.2  FILENAME REGEX  (canonical form)
  -------------------------------------

      ^(?P<chassis_no>[A-HJ-NPR-Z0-9]{17})_(?P<camera>[LR])(?:_\d+)?\.(jpg|jpeg|png)$

      Capture groups:
          chassis_no  : 5-character string-format identifier
                        (shown as "Product ID" in the UI)
          camera      : "L" (left, Cam1) or "R" (right, Cam2)

      Valid examples:
          MALB6_L.jpg
          M3456_R.jpg
          MALBB_L_001.jpg
          MALB06_R_001.jpg


  4.3  UI-LAYER TERMINOLOGY MAPPING
  ---------------------------------
      The backend calls the identifier "chassis_no"; the UI displays
      it as "Product ID" in the tables and detail views to match
      customer nomenclature. It is the same value — only the label
      differs. See Section 10.3 for the full terminology mapping
      (status labels, camera labels, etc.).



================================================================================
  5. DATA SCHEMA CONTRACTS
================================================================================

  5.1  IMAGE CONTRACT  (raw input from the capture system)
  --------------------------------------------------------

      attribute           requirement
      ------------------  -----------------------------------------------
      file_format         JPEG (.jpg, .jpeg) or PNG (.png)
      colour_space        RGB (3 channels)
      resolution_min      2048 x 1536 px
      resolution_max      4096 x 3072 px
      bit_depth           8 bits per channel
      file_size_max       15 MB
      naming              see Section 4.2
      blur_laplacian      variance >= 100
      exposure_mean       within [40, 220]


  5.2  SESSION RECORD  (persisted)
  --------------------------------

      column              type          nullable  notes
      ------------------  ------------  --------  -------------------------
      session_id          UUID          NO        primary key
      started_at          TIMESTAMPTZ   NO        session open time
      stopped_at          TIMESTAMPTZ   YES       null until /stop
      started_by          VARCHAR(64)   NO        caller identity
      status              VARCHAR(16)   NO        ACTIVE | STOPPED | FAILED
      left_dir            TEXT          NO        absolute folder path
      right_dir           TEXT          NO        absolute folder path
      algo_params_version VARCHAR(32)   NO        parameter set in effect
      shift               VARCHAR(8)    YES       "A"|"B"|"C"  (optional)
      area                VARCHAR(32)   YES       e.g. "Welding"
      notes               TEXT          YES       free-form operator note


  5.3  PER-CAMERA MEASUREMENT RECORD  (persisted)
  -----------------------------------------------

      column              type          nullable  notes
      ------------------  ------------  --------  -------------------------
      measurement_id      UUID          NO        primary key
      session_id          UUID          NO        FK to session
      chassis_no          VARCHAR(17)   NO        indexed; displayed as
                                                  "Product ID"
      camera_side         CHAR(1)       NO        "L" (Cam1) or "R" (Cam2)
      image_path          TEXT          NO        source image
      diameter_mm         NUMERIC(6,3)  YES       null when status=ERROR
      tolerance_min_mm    NUMERIC(6,3)  NO        snapshot at measure time
      tolerance_max_mm    NUMERIC(6,3)  NO        snapshot at measure time
      status              VARCHAR(16)   NO        PASS | FAIL | REVIEW | ERROR
      confidence_score    NUMERIC(4,3)  YES       in [0.000, 1.000]
      circle_center_x_px  INTEGER       YES       geometry (audit)
      circle_center_y_px  INTEGER       YES       geometry (audit)
      radius_px           NUMERIC(8,3)  YES       sub-pixel radius
      mm_per_px           NUMERIC(8,6)  NO        calibration used
      calibration_version VARCHAR(32)   NO        e.g. "cal-2026-03-14"
      algo_params_version VARCHAR(32)   NO        parameter set in effect
      debug_image_path    TEXT          YES       annotated image
      error_code          VARCHAR(32)   YES       populated when status=ERROR
      error_message       TEXT          YES       human-readable detail
      processed_at        TIMESTAMPTZ   NO        when measurement finished
      latency_ms          INTEGER       NO        per-image processing time


  5.4  CHASSIS (AGGREGATE) RECORD  (persisted)
  --------------------------------------------

      column                type          nullable  notes
      --------------------  ------------  --------  -----------------------
      chassis_record_id     UUID          NO        primary key; used in UI
                                                    routes as the "id" in
                                                    /home/details/:id
      session_id            UUID          NO        FK to session
      chassis_no            VARCHAR(17)   NO        indexed
      left_measurement_id   UUID          YES       FK, null if missing
      right_measurement_id  UUID          YES       FK, null if missing
      left_diameter_mm      NUMERIC(6,3)  YES
      right_diameter_mm     NUMERIC(6,3)  YES
      avg_diameter_mm       NUMERIC(6,3)  YES       null if either side null
      asymmetry_mm          NUMERIC(6,3)  YES       |left - right|
      overall_status        VARCHAR(16)   NO        PASS | FAIL | REVIEW | ERROR
      operator_decision     VARCHAR(16)   YES       CORRECT | INCORRECT | null
      decided_by            VARCHAR(64)   YES       operator id
      decided_at            TIMESTAMPTZ   YES
      flagged               BOOLEAN       NO        default false
      aggregated_at         TIMESTAMPTZ   NO        when both sides were
                                                    joined


  5.5  CALIBRATION RECORD  (per camera)
  -------------------------------------

      Every measurement MUST reference an active calibration for the
      camera side in use. The service refuses to start a session if
      either camera lacks an active calibration.

      field            requirement
      ---------------  -----------------------------------------------
      calibration_id   VARCHAR(32)   e.g. "cal-2026-03-14-L"
      camera_side      CHAR(1)       "L" or "R"
      mm_per_px        NUMERIC(8,6)  conversion factor
      method           VARCHAR(32)   "checkerboard" | "reference-part"
      valid_from       TIMESTAMPTZ   calibration timestamp
      operator         VARCHAR(64)   who ran the calibration
      reference_image  TEXT          path to the calibration image



================================================================================
  6. MEASUREMENT ALGORITHM DESIGN
================================================================================

  The measurement pipeline is deterministic given (image, calibration,
  algo_params). Non-determinism is forbidden — the same inputs must
  always produce the same measurement.


  ALGORITHM   |  measure_innermost_diameter  (algo-1.3.0, see ADR-008)
  ------------|-------------------------------------------------------

    INPUT   : image          (validated, within the contract of 5.1)
              calibration    (mm_per_px for the image's camera_side)
              algo_params    (threshold, morphology, contour, hough,
                              target, tolerance)
    OUTPUT  : MeasurementResult  (see schema 5.3)


    step 01 |  Load the image; convert to grayscale.
    step 02 |  Apply Gaussian blur (kernel from algo_params) to
               suppress sensor noise.
    step 03 |  Apply adaptive Gaussian threshold, inverted, so that
               dark holes in the plate become white (255) foreground
               and the bright plate becomes black (0) background.
               Parameters: block_size and c from algo_params.threshold.
    step 04 |  Morphological close (kernel_size, iterations from
               algo_params.morphology) to fill small gaps in the
               foreground so each hole is a single closed contour.
    step 05 |  Extract external contours. Drop any whose area is
               below algo_params.contour.min_area. Sort the remaining
               contours largest-area first.
    step 06 |  For each contour in that order:
                  a) Fill the contour into a binary mask.
                  b) AND-mask it onto the grayscale image.
                  c) Run cv2.HoughCircles on the masked grayscale,
                     with radius window
                         minRadius = (target - radius_tol) / 2 * ppm
                         maxRadius = (target + radius_tol) / 2 * ppm
                     where ppm = 1 / mm_per_px and target/radius_tol
                     come from algo_params.target.
                  d) If Hough returns at least one circle, take the
                     first one and stop iterating.
    step 07 |  If no contour yielded a matching circle, return
               status=ERROR with error_code=ERR_NO_CIRCLE.
    step 08 |  Convert radius_px to diameter_mm using mm_per_px from
               the camera's active calibration.
    step 09 |  Classify by distance from the target:
                 if diameter < tolerance_min_mm or
                    diameter > tolerance_max_mm
                     -> status = FAIL    (UI label: "Not Okay")
                 elif |diameter - target| <= ok_band_mm
                     -> status = PASS    (UI label: "Okay")
                 elif |diameter - target| <= somewhat_ok_band_mm
                     -> status = REVIEW  (UI label: "Somewhat Okay")
                 else
                     -> status = FAIL    (UI label: "Not Okay")
               (No measurement at all -> status=ERROR with code
                ERR_NO_CIRCLE, as in step 07.)
    step 10 |  Compute an informational confidence score:
                 confidence = 1 - |diameter - target| / somewhat_ok_band_mm
               clamped to [0, 1]. It is shown to operators on the
               Violation Detail page but does not drive status.
    step 11 |  Render an annotated debug image with the selected
               circle highlighted in the status colour, a reference
               target circle drawn around the same centre at the
               target diameter for visual comparison, the measured
               diameter in mm as a text overlay, and the confidence
               score.
    step 12 |  Persist the MeasurementResult and the debug image;
               return to caller.


  DETERMINISM GUARANTEES
  ----------------------
    - No stochastic sampling anywhere in the pipeline (RANSAC was
      removed in algo-1.3.0; see ADR-008). Same input = same output.
    - No time-based logic anywhere in the algorithm.
    - algo_params and calibration_version are pinned per measurement
      record; changing them requires a version bump (see Section 11).



================================================================================
  7. DUAL-CAMERA RESULT AGGREGATION
================================================================================

  Each chassis is photographed by both a left camera (Cam1) and a
  right camera (Cam2). The service emits two kinds of results:

      per-camera result    : emitted as soon as one image is processed
      chassis result       : emitted when both sides have been processed


  7.1  AGGREGATION RULES
  ----------------------

      let L = per-camera result from the LEFT image (Cam1)
      let R = per-camera result from the RIGHT image (Cam2)

      avg_diameter_mm  = (L.diameter + R.diameter) / 2
                         (null if either side is null)

      asymmetry_mm     = | L.diameter - R.diameter |
                         (null if either side is null)

      overall_status matrix:

          L\R        PASS      REVIEW     FAIL      ERROR
          PASS       PASS      REVIEW     FAIL      ERROR
          REVIEW     REVIEW    REVIEW     FAIL      ERROR
          FAIL       FAIL      FAIL       FAIL      FAIL
          ERROR      ERROR     ERROR      FAIL      ERROR

      plus: if asymmetry_mm > asymmetry_threshold (config, default
      0.15 mm), downgrade overall_status from PASS to REVIEW.


  7.2  HANDLING MISSING SIDES WITHIN A SESSION
  --------------------------------------------

      If a session is stopped while some chassis has only one side
      processed, the aggregator emits a chassis_result with
      overall_status=REVIEW and a reason field of "missing side: L"
      or "missing side: R".



================================================================================
  8. API SPECIFICATION
================================================================================

  The CV service exposes session-lifecycle endpoints, read endpoints
  that power the Dashboard, a per-chassis lookup for the Violation
  Detail page, and operational probes. All endpoints are internal
  to the plant network.


  8.1  POST /v1/sessions/start
  ----------------------------
       purpose : open a new processing session; begin monitoring the
                 configured left and right folders
       auth    : mTLS + service token

       request body (JSON):
           {
             "started_by": "operator-42",
             "shift":      "A",
             "area":       "Welding",
             "notes":      "shift A, line 1"
           }

       response 201 (JSON):
           {
             "session_id":          "9b4e...",
             "status":              "ACTIVE",
             "left_dir":            "/images/left",
             "right_dir":           "/images/right",
             "algo_params_version": "algo-1.2.0",
             "left_calibration":    "cal-2026-03-14-L",
             "right_calibration":   "cal-2026-03-14-R",
             "started_at":          "2026-04-16T09:10:00Z"
           }


  8.2  POST /v1/sessions/{session_id}/stop
  ----------------------------------------
       Returns a summary (see v2.0, unchanged).


  8.3  GET /v1/sessions/{session_id}/events        (Server-Sent Events)
  ---------------------------------------------------------------------
       Real-time stream of measurement events for the UI log. See
       Section 9 for the event schema.


  8.4  GET /v1/chassis                      (NEW — powers the Dashboard table)
  ----------------------------------------------------------------------------
       purpose : paginated list of chassis records for the Production
                 Details table on the Dashboard
       query   : ?from=<iso>&to=<iso>&status=<PASS|REVIEW|FAIL|ERROR>
                 &shift=<A|B|C>&search=<prefix>&page=<n>&page_size=<n>
       response:
           {
             "page":       1,
             "page_size":  10,
             "total":      87,
             "items": [
               {
                 "chassis_record_id": "...",
                 "chassis_no":        "MALBB51BLPM123456",
                 "overall_status":    "PASS",
                 "avg_diameter_mm":   47.315,
                 "timestamp":         "2026-02-09T13:04:20Z",
                 "shift":             "A",
                 "area":              "Welding",
                 "flagged":           false
               },
               ...
             ]
           }


  8.5  GET /v1/chassis/{chassis_record_id}  (NEW — powers Violation Detail)
  -------------------------------------------------------------------------
       purpose : full chassis record + both per-camera measurements
                 for the Violation Detail page
       response:
           {
             "chassis_record_id": "...",
             "chassis_no":        "MALBB51BLPM123456",
             "overall_status":    "PASS",
             "flagged":           false,
             "timestamp":         "2026-02-09T13:04:20Z",
             "shift":             "A",
             "area":              "Welding",
             "left":  {
               "measurement_id":  "...",
               "diameter_mm":     47.328,
               "status":          "PASS",
               "confidence":      0.94,
               "debug_image_url": "/v1/debug/<left_id>"
             },
             "right": {
               "measurement_id":  "...",
               "diameter_mm":     47.302,
               "status":          "PASS",
               "confidence":      0.93,
               "debug_image_url": "/v1/debug/<right_id>"
             }
           }


  8.6  POST /v1/chassis/{chassis_record_id}/decision     (NEW — operator)
  -----------------------------------------------------------------------
       purpose : record the operator's "Correct Violation" /
                 "Incorrect Violation" decision from the Violation
                 Detail page
       request :
           { "decision": "CORRECT" | "INCORRECT", "decided_by": "op-42" }
       response: 200 with the updated record


  8.7  POST /v1/chassis/{chassis_record_id}/flag          (NEW — operator)
  ------------------------------------------------------------------------
       purpose : toggle the "Flagged" state on a chassis
       request :
           { "flagged": true | false, "by": "op-42" }
       response: 200 with the updated record


  8.8  GET /v1/dashboard/summary             (NEW — powers the KPI cards)
  -----------------------------------------------------------------------
       purpose : aggregate counts for the Dashboard top row
       query   : ?from=<iso>&to=<iso>   (default: today)
       response:
           {
             "total":          87,
             "pass":           44,
             "review":         35,
             "fail":            8,
             "violation_pct":   9.20,
             "trend": [
               { "date": "2026-01-26", "review": 25, "fail": 40 },
               { "date": "2026-01-27", "review": 18, "fail": 28 },
               ...
             ],
             "recent_alerts": [
               {
                 "chassis_record_id": "...",
                 "chassis_no":        "MALBB51BLPM012890",
                 "timestamp":         "2026-02-09T09:59:10Z",
                 "overall_status":    "REVIEW"
               },
               ...
             ]
           }


  8.9  GET /v1/debug/{measurement_id}
  -----------------------------------
       Streams the annotated debug image (JPEG). Used by the
       Violation Detail page to render Cam1 and Cam2 images.


  8.10 GET /v1/health       GET /v1/ready
  ---------------------------------------
       Liveness and readiness probes — ready=200 only when both
       calibrations are active and both image folders are reachable.


  ERROR CODES (unchanged from v2.0; see that release for the full list.)



================================================================================
  9. REAL-TIME LOGGING TO THE FRONTEND
================================================================================

  The frontend receives a live feed of measurement events so that operators
  can monitor produce as it is measured. The primary delivery mechanism is
  Server-Sent Events (SSE); a polling endpoint is provided as a fallback.
  For the rendering behaviour of these events on the Dashboard, see
  Section 10.


  9.1  EVENT STREAM  (SSE on /v1/sessions/{session_id}/events)
  ------------------------------------------------------------

       event: session_opened
           { "session_id", "started_at", "algo_params_version",
             "left_calibration", "right_calibration" }

       event: camera_result
           {
             "measurement_id":   "...",
             "chassis_no":       "MALBB51BLPM123456",
             "camera_side":      "L",             // UI renders as "Cam1"
             "diameter_mm":      47.328,
             "status":           "PASS",          // UI renders as "Okay"
             "confidence_score": 0.94,
             "processed_at":     "2026-02-09T13:04:25Z",
             "debug_image_url":  "/v1/debug/..."
           }

       event: chassis_result
           {
             "chassis_record_id":  "...",         // used as route id in UI
             "chassis_no":         "MALBB51BLPM123456",
             "left_diameter_mm":   47.328,
             "right_diameter_mm":  47.302,
             "avg_diameter_mm":    47.315,
             "asymmetry_mm":       0.026,
             "overall_status":     "PASS",        // UI renders as "Okay"
             "shift":              "A",
             "area":               "Welding",
             "aggregated_at":      "2026-02-09T13:04:28Z"
           }

       event: warning
           { "chassis_no", "file", "error_code", "message" }

       event: session_closed
           { "session_id", "stopped_at", "summary": { ... } }


  9.2  FRONTEND REACTION TO EVENTS
  --------------------------------
       - chassis_result events prepend a row to the Production Details
         table on the Dashboard and update the three KPI cards.
       - camera_result events do not directly render rows on the
         Dashboard; they are used only by the Violation Detail page
         (and to power the "Recent Alerts" widget when the status is
         REVIEW or FAIL).
       - warning events update a small warning indicator in the
         header and are available under Settings -> Warnings.



================================================================================
  10. FRONTEND APPLICATION ARCHITECTURE                               (NEW)
================================================================================

  The frontend is a two-page single-page application (SPA). Intentionally
  simple: one developer should be able to scaffold and ship it in days,
  not weeks. The UI in the approved mockups is the target.


  10.1  DESIGN INTENT
  -------------------
      - TWO pages only:
          * PAGE 1 — Dashboard                   route: /home
          * PAGE 2 — Violation Detail            route: /home/details/:id
      - The header (logo + nav + user menu) is shared across both pages.
      - The nav has three tabs: Home, Live View, Settings. For v1, only
        "Home" is implemented; "Live View" and "Settings" are placeholders
        shown disabled or stubbed so we ship the header complete.
      - Real-time behaviour: the Dashboard subscribes to the current
        active session's SSE stream and updates KPI cards and the table
        without a page refresh.


  10.2  FRONTEND TECHNOLOGY STACK  (PINNED)
  -----------------------------------------

       package              pinned version    purpose
       -------------------  ----------------  --------------------------
       React                18.3.*            UI framework
       Vite                 5.4.*             dev server + production
                                              build, fast HMR
       React Router DOM     6.26.*            routing between the two
                                              pages
       TypeScript           5.5.*             type safety (optional but
                                              recommended)
       Tailwind CSS         3.4.*             utility-first styling
       @headlessui/react    2.1.*             accessible dropdowns,
                                              dialogs (filters, modals)
       lucide-react         0.441.*           icon set (download,
                                              flag, arrow-back, etc.)
       Recharts             2.12.*            donut chart, line chart
       @tanstack/react-     8.20.*            headless table primitives
        table                                 (sorting, pagination)
       Axios                1.7.*             HTTP client
       (native EventSource) ----              SSE subscription
       date-fns             3.6.*             date formatting

       Dev-only:
       Prettier             3.3.*
       ESLint               9.x
       Vitest               2.x               unit tests
       Playwright           1.x               a couple of E2E smoke tests

       WHY THESE
       - React + Vite + Tailwind is the mainstream low-ceremony stack.
       - Recharts is declarative and renders the donut and line charts
         in the mockups with very little code.
       - @tanstack/react-table gives us sorting and pagination without
         dragging in a full data-grid.
       - No state-management library. React's built-in useState,
         useReducer, and useContext are sufficient for two pages.
       - No UI component library like MUI. Tailwind + headless
         primitives keeps the bundle small and the look close to the
         mockups.


  10.3  TERMINOLOGY MAPPING (BACKEND -> UI)
  -----------------------------------------

       BACKEND VALUE            UI LABEL                    COLOUR
       -----------------------  --------------------------  ------------
       status = PASS            "Okay"                      green
       status = REVIEW          "Somewhat Okay"             amber
       status = FAIL            "Not Okay"                  red
       status = ERROR           "Error"                     grey
       camera_side = L          "Cam1"                      --
       camera_side = R          "Cam2"                      --
       chassis_no               "Product ID"                --
       chassis_record_id        "Violation ID" (in detail)  --

       The mapping is implemented in one place: src/ui/labels.ts.
       Do NOT scatter hard-coded status strings around components.


  10.4  PAGE 1 — DASHBOARD (/home)
  --------------------------------

      Four regions, top to bottom:

      REGION A — HEADER  (shared)
         - Left:   algo8 logo + "MARUTI" wordmark
         - Middle: nav tabs (Home active, Live View, Settings)
         - Right:  user icon with menu (profile / logout)

      REGION B — KPI ROW  (three cards side by side)

         Card B1: "Violations Today"
           - Donut chart showing Okay / Somewhat Okay / Not Okay
           - Centre text: violation percentage (e.g. "9.20%")
           - Right-side legend with counts and Total
           - Data source: GET /v1/dashboard/summary
           - Recharts component: <PieChart> with <Pie> and <Cell>

         Card B2: "Violation Trend"
           - Two-line chart over the configured period (default 7 days)
           - Line 1: "Not Okay" (red)
           - Line 2: "Somewhat Okay" (amber)
           - X-axis: date (formatted DD/MM)
           - Data source: GET /v1/dashboard/summary (trend array)
           - Recharts component: <LineChart> with two <Line>s

         Card B3: "Recent Alerts"
           - Vertical list of most recent REVIEW/FAIL chassis
           - Each row: timestamp + chassis_no summary + link icon
           - Clicking an alert navigates to /home/details/:id
           - Data source: GET /v1/dashboard/summary (recent_alerts)

      REGION C — PRODUCTION DETAILS  (table with controls)

         Header row above the table:
           - Title "Production Details" + item count (e.g. "87 items")
           - Quick-range buttons: [Today] [Past 7 Days] [Date Range v]
           - Dropdown: "Shift :  All v"
           - Dropdown: "Condition :  All v"
           - Search input with magnifying-glass icon
           - Export icon button (downloads CSV via /v1/chassis?...&format=csv)

         Table columns:
           1. Overall Condition    (pill with color + text — mapped via 10.3)
           2. Timestamp            (DD/MM/YYYY HH:MM:SS)
           3. Product ID           (chassis_no; monospace)
           4. Shift                ("A" / "B" / "C")
           5. Area                 (e.g. "Welding")

         Each row is clickable; clicking opens /home/details/:id where
         id is the chassis_record_id.

         Footer row:
           - Left:  "Showing: [10 v] items per page"
           - Right: "Page: [<] 1 of 9 [>]"

         Data source: GET /v1/chassis?from=...&to=...&status=...&shift=...
         &search=...&page=1&page_size=10

      REGION D — LIVE UPDATE WIRING
         - On mount, the Dashboard discovers the current ACTIVE
           session via GET /v1/sessions?status=ACTIVE (returns 0 or 1
           session for v1).
         - If an ACTIVE session exists, the Dashboard opens an
           EventSource on /v1/sessions/{id}/events.
         - On each chassis_result event: prepend the row to the
           Production Details table and invalidate the KPI card data
           (refetch summary).
         - On session_closed: close the EventSource; continue to show
           the table data from the last snapshot.


  10.5  PAGE 2 — VIOLATION DETAIL (/home/details/:id)
  ---------------------------------------------------

      Layout mirrors the mockup: back button, two camera cards on
      the left, a details panel on the right.

      REGION A — HEADER  (same shared header)

      REGION B — BACK AND TITLE
         - Back arrow (navigates() to /home)
         - Title: "Violation Detail"

      REGION C — TWO CAMERA CARDS (left + right, side by side)

         Each card shows:
           - Header strip: "Cam1" (or "Cam2") on the left,
             "Violation ID: <measurement_id>" on the right,
             maximise icon on the far right.
           - Large image area: the annotated debug image
             (<img src="/v1/debug/{measurement_id}"/> with lazy load
             and a fallback placeholder).
           - Condition row: "Condition" label on the left,
             "Okay" / "Somewhat Okay" / "Not Okay" on the right
             in the status colour.
           - Two action buttons at the bottom:
                [ Incorrect Violation ]   [ Correct Violation ]
             - Tapping either posts to
               POST /v1/chassis/{id}/decision with
               {decision: "INCORRECT"|"CORRECT"}. The card shows a
               subtle confirmation and the chosen button becomes
               "selected" visually. A second tap toggles the choice.

      REGION D — VIOLATION DETAIL PANEL (right side)

         A card with:
           - Title "Violation Detail"
           - "Flagged" toggle button (top right) that calls
             POST /v1/chassis/{id}/flag with the new state
           - Download button (top right) that fetches a PDF/ZIP
             bundle for the chassis (both debug images + metadata).
             For v1, implement as a JSON download; PDF packaging is
             a later improvement.
           - Key-value list:
                Product ID          <chassis_no>
                Overall Condition   <status mapped to UI label>
                Timestamp           <formatted>
                Shift               <A/B/C>
                Area                <string>

         Data source: GET /v1/chassis/{id} (single call returns both
         per-camera measurements and the chassis summary).


  10.6  FRONTEND DIRECTORY STRUCTURE
  ----------------------------------

      frontend/
      |-- index.html
      |-- vite.config.ts
      |-- tailwind.config.ts
      |-- postcss.config.cjs
      |-- tsconfig.json
      |-- package.json
      |
      |-- src/
      |   |-- main.tsx                 <- ReactDOM.createRoot
      |   |-- App.tsx                  <- <BrowserRouter> + routes
      |   |-- api/
      |   |   |-- client.ts            <- axios instance, base URL
      |   |   |-- dashboard.ts         <- GET /v1/dashboard/summary,
      |   |   |                           GET /v1/chassis (list)
      |   |   |-- chassis.ts           <- GET /v1/chassis/:id,
      |   |   |                           POST decision, POST flag
      |   |   |-- sessions.ts          <- start/stop, active session
      |   |   |-- sse.ts               <- EventSource hook wrapper
      |   |-- hooks/
      |   |   |-- useLiveSession.ts    <- connects + listens for events
      |   |   |-- useChassisList.ts
      |   |-- pages/
      |   |   |-- Dashboard.tsx
      |   |   |-- ViolationDetail.tsx
      |   |-- components/
      |   |   |-- Header.tsx
      |   |   |-- StatusPill.tsx       <- PASS/REVIEW/FAIL -> UI label
      |   |   |-- KpiDonut.tsx         <- Recharts PieChart
      |   |   |-- KpiTrend.tsx         <- Recharts LineChart
      |   |   |-- AlertsList.tsx
      |   |   |-- FiltersBar.tsx       <- date range, shift, condition,
      |   |   |                           search
      |   |   |-- ProductionTable.tsx  <- @tanstack/react-table
      |   |   |-- Pagination.tsx
      |   |   |-- CameraCard.tsx       <- image + condition + buttons
      |   |   |-- DetailPanel.tsx      <- KV list, flagged, download
      |   |-- labels.ts                <- status + camera UI mapping
      |   |-- routes.ts                <- route constants
      |   |-- styles/
      |       |-- index.css            <- tailwind @layer base
      |
      |-- tests/
      |   |-- unit/
      |   |-- e2e/                     <- Playwright smoke tests


  10.7  ROUTING CONFIGURATION
  ---------------------------

      <BrowserRouter>
        <Routes>
          <Route path="/"       element={<Navigate to="/home" />} />
          <Route path="/home"   element={<Dashboard />} />
          <Route path="/home/details/:id"
                                element={<ViolationDetail />} />
          <Route path="*"       element={<NotFound />} />
        </Routes>
      </BrowserRouter>

      The Header component reads location via useLocation and
      highlights the current tab. "Live View" and "Settings" are
      registered as placeholders that render a "Coming soon" panel in
      v1 so the header remains intact.


  10.8  STATE MANAGEMENT
  ----------------------

      - Local component state (useState) for UI state (open dropdowns,
        search text, selected filters).
      - One React Context for the live session state:
          SessionContext = {
            session: Session | null,
            connected: boolean,
            lastEvent: Event | null,
          }
        Provided once in App.tsx; subscribes to SSE from useLiveSession.
      - Server state is kept simple: each page fetches what it needs on
        mount and refetches on relevant events. No React Query in v1
        (optional later if caching becomes a burden).


  10.9  STATUS PILL COMPONENT  (sketch)
  -------------------------------------

      // src/components/StatusPill.tsx
      import { STATUS_LABEL, STATUS_COLOR } from "../labels";
      type Props = { status: "PASS" | "REVIEW" | "FAIL" | "ERROR" };
      export function StatusPill({ status }: Props) {
        return (
          <span className={`inline-flex items-center gap-2 rounded-full
                            px-2 py-0.5 text-xs font-medium
                            ${STATUS_COLOR[status]}`}>
            {status === "REVIEW" && <FlagIcon className="h-3 w-3" />}
            {STATUS_LABEL[status]}
          </span>
        );
      }

      // src/labels.ts
      export const STATUS_LABEL = {
        PASS:   "Okay",
        REVIEW: "Somewhat Okay",
        FAIL:   "Not Okay",
        ERROR:  "Error",
      } as const;
      export const STATUS_COLOR = {
        PASS:   "text-green-700 bg-green-50",
        REVIEW: "text-amber-700 bg-amber-50",
        FAIL:   "text-red-700   bg-red-50",
        ERROR:  "text-gray-700  bg-gray-100",
      } as const;


  10.10  SSE HOOK  (sketch)
  -------------------------

      // src/hooks/useLiveSession.ts
      export function useLiveSession(sessionId: string | null) {
        const [lastEvent, setLastEvent] = useState<any>(null);
        const [connected, setConnected] = useState(false);

        useEffect(() => {
          if (!sessionId) return;
          const url = `/v1/sessions/${sessionId}/events`;
          const es = new EventSource(url);
          es.onopen    = () => setConnected(true);
          es.onerror   = () => setConnected(false);
          es.addEventListener("camera_result",   (e) =>
            setLastEvent({ type: "camera_result",   data: JSON.parse(e.data) }));
          es.addEventListener("chassis_result",  (e) =>
            setLastEvent({ type: "chassis_result", data: JSON.parse(e.data) }));
          es.addEventListener("warning",         (e) =>
            setLastEvent({ type: "warning",        data: JSON.parse(e.data) }));
          es.addEventListener("session_closed",  (e) =>
            setLastEvent({ type: "session_closed", data: JSON.parse(e.data) }));
          return () => es.close();
        }, [sessionId]);

        return { lastEvent, connected };
      }

      Consumers invalidate their relevant queries when lastEvent
      changes (Dashboard re-fetches /dashboard/summary and /chassis
      on a "chassis_result" event).


  10.11  BUILD AND DEPLOYMENT
  ---------------------------

      - Dev:        `pnpm dev` or `npm run dev` (Vite on :5173).
      - Build:      `pnpm build` produces a static bundle in /dist.
      - Serve:      the backend FastAPI app serves /dist behind the
                    same origin (/) and proxies /v1/* to itself.
                    Alternatively, use nginx in the same container.
      - Same-origin deployment sidesteps CORS and cookie issues.
      - The frontend is bundled into the backend Docker image as
        part of the CI build; one image ships both.


  10.12  ACCESSIBILITY AND RESPONSIVENESS
  ---------------------------------------

      - Status is never conveyed by colour alone; the label text is
        always present next to the coloured pill.
      - All interactive elements have accessible labels (aria-label).
      - Tab order follows the visual order on both pages.
      - The layout is responsive to station-tablet widths (1280px
        minimum supported). Mobile is out of scope.


  10.13  FRONTEND OUT OF SCOPE (v1)
  ---------------------------------

      - "Live View" and "Settings" pages beyond placeholders.
      - Role-based access control in the UI (assumed upstream).
      - Internationalisation beyond the default locale.
      - PDF export (v1 provides JSON download; PDF is a follow-up).
      - Multi-station coordination in a single UI view.



================================================================================
  11. ALGORITHM PARAMETERS AND CALIBRATION VERSIONING
================================================================================

  Because the pipeline is fully classical, there are no model weights to
  version. Instead, two artefacts are versioned explicitly:


  11.1  ALGORITHM PARAMETER SET  (algo_params)
  --------------------------------------------

     Stored as YAML in configs/algo_params/<version>.yaml.
     Every session pins one algo_params_version. Every measurement
     record stores the version it used. Changing any value requires a
     version bump and an ADR entry.

     algo_params.yaml (example, algo-1.3.0; see ADR-008):

        version: "algo-1.3.0"
        blur:
          kernel: 5
        threshold:
          block_size: 51       # adaptive Gaussian threshold window
          c: 10                # constant subtracted from local mean
        morphology:
          kernel_size: 3
          iterations: 1
        contour:
          min_area: 50.0
        hough:
          dp: 1.2
          min_dist: 10
          param1: 50
          param2: 20
        target:
          diameter_mm: 47.25
          radius_tolerance_mm: 0.30   # Hough radius window
        tolerance:
          min_mm: 47.000
          max_mm: 47.500
          ok_band_mm: 0.20            # PASS when |delta| <= ok_band_mm
          somewhat_ok_band_mm: 0.50   # REVIEW when ok < |delta| <= somewhat_ok
          asymmetry_threshold_mm: 0.15


  11.2  CALIBRATION RECORDS  (per camera side)
  --------------------------------------------

     One active calibration per side. Switching to a new calibration is
     a deliberate action (script + approval). Historical calibrations
     are retained so past measurements remain reproducible.



================================================================================
  12. PROJECT STRUCTURE AND SCAFFOLDING
================================================================================

  The backend repository structure is unchanged from v2.0 (see that TRD
  version's Section 11 for the full tree). The frontend lives in a
  sibling directory:

  trailing-arm-detection/
  |-- backend/            <- the Python service (unchanged)
  |-- frontend/           <- the React SPA (see Section 10.6)
  |-- configs/            <- algo_params + calibration YAML
  |-- docs/
  |-- .github/workflows/
      |-- ci-backend.yml
      |-- ci-frontend.yml
      |-- cd.yml          <- builds one image with both artefacts

  The backend serves the frontend's built assets from /dist at the
  root path; /v1/* is reserved for the API.



================================================================================
  13. CLAUDE.md — PROJECT MEMORY FILE
================================================================================

  CLAUDE.md is the first file committed in the repository. It contains
  just enough context for any future Claude Code session to be productive
  in the first message. A template is provided in Appendix B and the
  frontend-specific entries (pinned React/Vite versions, routes,
  terminology mapping) are included.



================================================================================
  14. ARCHITECTURE DECISION RECORDS (ADRs)
================================================================================

  Every non-obvious choice is recorded as an ADR in docs/decisions/.
  Numbered sequentially. Immutable once approved; superseded ADRs link
  to their replacement. Template in Appendix C.


  ADR-001  |  Classical CV only — no machine learning
  ---------------------------------------------------
     (Unchanged from v2.0.)


  ADR-002  |  Chassis number parsed from filename
  -----------------------------------------------
     (Unchanged from v2.0.)


  ADR-003  |  Session-based API with SSE event stream
  ---------------------------------------------------
     (Unchanged from v2.0.)


  ADR-004  |  Dual-camera aggregation keyed by chassis_no
  -------------------------------------------------------
     (Unchanged from v2.0.)


  ADR-005  |  Version pinning: algo_params + calibration per measurement
  ----------------------------------------------------------------------
     (Unchanged from v2.0.)


  ADR-006  |  Storage: Postgres + MinIO, on-premises
  --------------------------------------------------
     (Unchanged from v2.0.)


  ADR-007  |  Frontend stack: React + Vite + Tailwind + Recharts
  --------------------------------------------------------------
     context      : The UI is a simple two-page application (Dashboard
                    + Violation Detail) with one real-time surface (the
                    dashboard table and KPI cards). A heavy framework
                    would cost more than it returns.
     decision     : Build the frontend as a Vite-powered React SPA,
                    styled with Tailwind CSS, charted with Recharts,
                    tabled with @tanstack/react-table, and routed with
                    React Router v6.
     alternatives : Next.js (overkill for two pages and server
                    rendering not needed); plain HTML + Alpine.js
                    (cheap to start but harder to maintain as features
                    grow); a commercial UI kit (heavier bundle,
                    visual drift from the approved mockups).
     consequences : One developer can scaffold in a day; the bundle
                    stays small; the team already knows React. We
                    accept a small build step (Vite) in exchange for
                    type safety and component reuse.


  ADR-008  |  Contour + masked Hough (replaces Canny + pick_innermost
            + RANSAC)
  --------------------------------------------------------------------
     context      : The original Canny -> HoughCircles ->
                    pick_innermost -> RANSAC refine recipe works on
                    synthetic fixtures but breaks on real trailing-arm
                    images. Textured industrial surfaces produce
                    500-800 phantom circles; pick_innermost picks the
                    smallest one (noise) instead of the bushing.
     decision     : Use Gaussian blur -> adaptive Gaussian threshold
                    (inverted) -> morphological close -> external
                    contours largest-first -> for each contour, run
                    cv2.HoughCircles constrained to
                    target_diameter_mm +/- radius_tolerance_mm.
                    Status is derived from the diameter band, not
                    a Hough/RANSAC confidence product.
     alternatives : (1) Keep RANSAC, raise param2 globally — still
                    picks the wrong circle; (2) ML-based ROI detector
                    before measurement — rejected by ADR-001.
     consequences : Deterministic (no RANSAC sampling). Lower CPU
                    cost (no 200-iteration RANSAC inner loop).
                    Requires a known target diameter in algo_params.
                    Schema of algo_params YAML changes incompatibly,
                    so algo-1.2.0.yaml is removed and algo-1.3.0.yaml
                    is the new canonical.
     references   : docs/decisions/ADR-008.md for the full record,
                    including before/after evidence on the real
                    cam18jdleofhtlhj6_{L,R}.jpg fixtures.



================================================================================
  15. INFRASTRUCTURE REQUIREMENTS
================================================================================

  (Contents unchanged from v2.0. Frontend runs as static assets served
  by the backend; no additional infra footprint.)


  15.1  ENVIRONMENTS
  ------------------

       environment   purpose                       hardware
       -----------   ----------------------------  -------------------------
       local         developer laptops             any x86_64, 16 GB RAM
       dev           shared development cluster    4 vCPU, 16 GB
       staging       pre-prod mirror of plant      8 vCPU, 32 GB
       production    plant server                  8 vCPU, 32 GB, NVMe


  15.2  CONTAINERISATION
  ----------------------
       base image   : python:3.11-slim + nginx sidecar (or a single
                      multi-stage image that serves static /dist from
                      the same FastAPI app)
       size target  : < 700 MB including the frontend bundle
       build        : multi-stage — step 1 builds the frontend with
                      Node 20, step 2 installs backend deps, final
                      stage copies both /app and /app/dist


  15.3  KEY TOOLS (PINNED)
  ------------------------

       Backend pinned versions are unchanged from v2.0 (Python 3.11,
       FastAPI 0.115, opencv-python 4.10, etc.). Frontend pinned
       versions are in Section 10.2.



================================================================================
  16. PERFORMANCE AND SLA REQUIREMENTS
================================================================================

  LATENCY BUDGET  (per image, classical pipeline — unchanged)
  -----------------------------------------------------------

       stage                        budget (p95)
       ---------------------------  ------------
       filename parse + validate         40 ms
       image load                       250 ms
       image quality gates               80 ms
       CLAHE + blur + Canny             180 ms
       HoughCircles                     180 ms
       innermost selection               20 ms
       RANSAC refinement                100 ms
       annotation + persistence         200 ms
       headroom                         450 ms
       TOTAL per image (p95)           1500 ms


  FRONTEND PERFORMANCE TARGETS  (new)
  -----------------------------------

       metric                        target
       ----------------------------  ----------------
       First contentful paint        <= 1.2 s
       Dashboard data visible        <= 1.5 s
       Violation Detail data ready   <= 1.0 s
       Event-to-row latency (SSE)    <= 500 ms
       Table sort / filter click     <= 100 ms client-side


  SERVICE LEVEL OBJECTIVES  (unchanged)
  -------------------------------------
       availability (per month)      99.5 %
       per-image p95 latency         <= 1.5 s
       per-image p99 latency         <= 3.0 s
       error rate (5xx on API)       <  0.5 %
       manual-review rate            <= 5 %
       false-PASS rate               <= 0.1 %


  ACCURACY TARGETS  (unchanged)
  -----------------------------
       MAE          <= 0.05 mm
       P95 error    <= 0.10 mm
       max error    <= 0.20 mm



================================================================================
  17. SECURITY, PRIVACY AND COMPLIANCE
================================================================================

  (Unchanged from v2.0.)

  - No PII in images.
  - Chassis numbers treated as confidential business data.
  - mTLS between frontend host and CV service; service token in
    X-Service-Token.
  - Secrets loaded only from env.
  - No production image data leaves the plant VLAN.
  - Measurement record table is append-only.

  FRONTEND-SPECIFIC NOTES
  -----------------------
  - The SPA does not store credentials in localStorage. Session is
    plant-internal and authenticated at the network layer (mTLS + IP
    allowlist). If a token is ever introduced, it is kept only in
    memory for the lifetime of the page.
  - No third-party analytics scripts. No CDN-loaded fonts (Tailwind
    ships with system-font stack or self-hosted fonts only).



================================================================================
  18. TESTING AND VALIDATION STRATEGY
================================================================================

  (Backend testing unchanged from v2.0.)


  18.1  EVAL DATASET  (LOCKED) — unchanged
  ----------------------------------------


  18.2  METRICS — unchanged
  -------------------------


  18.3  BACKEND TEST PYRAMID — unchanged
  --------------------------------------


  18.4  FRONTEND TESTING  (new)
  -----------------------------

     unit            : pure helpers (labels, formatters, status pill)
                       tested with Vitest.
     component       : visual components rendered in isolation with
                       stub props; event handlers verified.
     contract        : API client modules tested against a fake
                       backend (MSW) that serves the documented
                       response shapes.
     e2e smoke       : Playwright scripts for two flows:
                       (a) Dashboard loads, table populates, row
                           click navigates to detail page.
                       (b) Violation Detail renders both camera
                           images, a decision can be recorded.



================================================================================
  19. DEPLOYMENT AND ROLLOUT STRATEGY
================================================================================

  (Mostly unchanged from v2.0. The frontend is built and packaged into
  the same Docker image as the backend.)

  PACKAGING
  ---------
     - Multi-stage Docker build:
       stage 1 (node:20-alpine): install npm deps, run `vite build`,
       output /dist.
       stage 2 (python:3.11-slim): install backend deps, copy backend
       code, copy /dist from stage 1 to /app/dist.
     - One image tagged with git SHA.

  CI/CD PIPELINE
  --------------
     ci-backend.yml   : ruff + mypy + pytest unit + pytest integration
     ci-frontend.yml  : eslint + prettier --check + vitest + vite build
     eval.yml         : locked eval harness (unchanged)
     cd.yml           : on tag push, builds both, bundles one image,
                        pushes to registry, deploys to staging.

  ROLLOUT
  -------
     Identical to v2.0 rollout (deploy to staging, replay images,
     QA sign-off, rolling prod update, 24 h observation with
     auto-rollback). The frontend is promoted at the same time as
     the backend; no separate frontend deployment.



================================================================================
  20. MONITORING, DRIFT DETECTION AND RECALIBRATION
================================================================================

  (Unchanged from v2.0. Frontend adds a single metric:
  `frontend_sse_disconnects_total`, scraped from a backend endpoint
  that counts abrupt EventSource closures, which helps diagnose
  network issues on the plant floor.)



================================================================================
  21. DEPENDENCIES AND EXTERNAL SYSTEMS
================================================================================

     system                owner          interface           criticality
     --------------------  -------------  ------------------  -------------
     Frontend / UI         Frontend Team  Start/Stop + SSE    BLOCKING
                                          + REST (dashboard,
                                          chassis, decision,
                                          flag)
     Image capture         Plant Eng.     shared filesystem   BLOCKING
     Postgres (on-prem)    Platform Team  SQL                 BLOCKING
     MinIO (on-prem)       Platform Team  S3 API              BLOCKING
     Plant Prometheus      Platform Team  scrape              MONITORING
     Plant secret mgr      Platform Team  env injection       BLOCKING



================================================================================
  22. TECHNICAL RISKS AND MITIGATION
================================================================================

  (Unchanged from v2.0. One frontend-specific entry added.)

     Risk                                           Impact  Mitigation
     ---------------------------------------------  ------  -----------------
     Lighting variation breaks edge detection       HIGH    CLAHE +
                                                            adaptive Canny
     Calibration drift                              HIGH    weekly calibration
                                                            check
     Filename convention violated upstream          HIGH    ERR_BAD_FILENAME
                                                            + warnings
     Image written before fully flushed             MEDIUM  stability check
     Missing side at session-end                    MEDIUM  REVIEW emit
     Hough hyperparams not general                  MEDIUM  locked eval set
     Postgres latency spike                         MEDIUM  async writes
     Silent algo_params change                      HIGH    ADR-005
     SSE disconnects under flaky plant network      MEDIUM  client-side
                                                            auto-reconnect
                                                            with /results
                                                            catch-up endpoint
                                                            (new in this v2.1)



================================================================================
  23. TIMELINE AND MILESTONES
================================================================================

  (Revised to include frontend work — indicative only.)

     milestone                                      phase   duration
     ---------------------------------------------  ------  --------
     TRD sign-off (this document)                   2       -
     Backend scaffold + CLAUDE.md + CI skeleton     2       1 week
     Frontend scaffold (Vite + routes + header)     2       3 days
     Filename parser + image validator              3       3 days
     Calibration tooling + first calibration run    3       1 week
     Classical measurement pipeline v1              4       1 week
     Dashboard KPI cards + table (with mock data)   4       1 week
     Violation Detail page (with mock data)         4       3 days
     Eval harness locked, eval set measured         3-4     2 weeks
     Session lifecycle + dual-camera aggregator     4       1 week
     SSE event stream + dashboard live wiring       4       1 week
     Full frontend <-> backend integration          4       3 days
     Internal eval meets accuracy targets           5       3 days
     Staging deploy + replay validation             5       3 days
     QA sign-off (caliper vs system)                6       1 week
     Production rollout (one line first)            7       1 week
     Full production rollout                        7       -
     Monitoring, drift checks, first recalibration  8       ongoing



================================================================================
  24. GLOSSARY
================================================================================

     Trailing arm         The suspension component under inspection.
     Innermost circle     The smallest-radius circular feature within
                          the central region of the trailing arm image.
     Chassis number       17-character VIN-format identifier; parsed
                          from the image filename. In the UI it is
                          labelled "Product ID".
     Camera side          "L" (left, Cam1) or "R" (right, Cam2).
     Session              The interval between a Start API call and
                          its matching Stop.
     Per-camera result    Measurement from one image; emitted as soon
                          as the image is processed.
     Chassis result       Aggregate across both cameras for a single
                          chassis; emitted when both sides are done.
     Asymmetry            Absolute difference between the left and
                          right measurements (mm).
     Calibration          mm-per-pixel factor for a specific camera at
                          a point in time.
     CLAHE                Contrast-Limited Adaptive Histogram
                          Equalisation.
     Hough Circle         Classical voting-based circle detector
                          (cv2.HoughCircles).
     RANSAC               Random Sample Consensus.
     SSE                  Server-Sent Events — uni-directional event
                          stream used for real-time logging.
     algo_params          Versioned YAML of algorithm hyperparameters.
     Dashboard            The home page at /home.
     Violation Detail     The per-chassis page at /home/details/:id.
     Status labels        Backend PASS/REVIEW/FAIL/ERROR map to UI
                          labels Okay/Somewhat Okay/Not Okay/Error.
     ADR                  Architecture Decision Record.
     TRD                  Technical Requirements Document (this file).



================================================================================
  25. APPENDIX A — EXAMPLE API PAYLOADS
================================================================================

  (v2.0 payloads remain valid; see that section for start/stop, SSE
  camera_result and chassis_result. The new v2.1 payloads are listed
  below.)


  GET /v1/dashboard/summary  RESPONSE
  -----------------------------------
     HTTP/1.1 200 OK

     {
       "total":          87,
       "pass":           44,
       "review":         35,
       "fail":            8,
       "violation_pct":   9.20,
       "trend": [
         { "date": "2026-02-03", "review": 25, "fail": 40 },
         { "date": "2026-02-04", "review": 18, "fail": 28 }
       ],
       "recent_alerts": [
         {
           "chassis_record_id": "8f2a...",
           "chassis_no":        "MALBB51BLPM012890",
           "timestamp":         "2026-02-09T09:59:10Z",
           "overall_status":    "REVIEW"
         }
       ]
     }


  GET /v1/chassis?status=REVIEW&page=1&page_size=10  RESPONSE
  -----------------------------------------------------------
     {
       "page":       1,
       "page_size":  10,
       "total":      35,
       "items": [
         {
           "chassis_record_id": "...",
           "chassis_no":        "MALBB51BLPM130243",
           "overall_status":    "REVIEW",
           "avg_diameter_mm":   47.415,
           "timestamp":         "2026-02-09T13:02:38Z",
           "shift":             "A",
           "area":              "Welding",
           "flagged":           true
         }
       ]
     }


  GET /v1/chassis/{id}  RESPONSE  (drives Violation Detail page)
  --------------------------------------------------------------
     {
       "chassis_record_id": "a3f1c8d2-...",
       "chassis_no":        "MALBB51BLPM224694",
       "overall_status":    "PASS",
       "flagged":           false,
       "timestamp":         "2026-02-09T13:52:19Z",
       "shift":             "A",
       "area":              "Welding",
       "left":  {
         "measurement_id":  "25776...",
         "diameter_mm":     47.328,
         "status":          "PASS",
         "confidence":      0.94,
         "debug_image_url": "/v1/debug/25776..."
       },
       "right": {
         "measurement_id":  "25777...",
         "diameter_mm":     47.302,
         "status":          "PASS",
         "confidence":      0.93,
         "debug_image_url": "/v1/debug/25777..."
       }
     }


  POST /v1/chassis/{id}/decision  REQUEST
  ---------------------------------------
     { "decision": "CORRECT", "decided_by": "operator-42" }


  POST /v1/chassis/{id}/flag  REQUEST
  -----------------------------------
     { "flagged": true, "by": "operator-42" }



================================================================================
  26. APPENDIX B — CLAUDE.md TEMPLATE
================================================================================

  # Trailing Arm Detection

  Classical-CV service that measures the innermost circle diameter on
  a trailing arm, using dual-camera images (left + right). No machine
  learning. A session-based API starts folder monitoring; results stream
  to the frontend in real time via SSE. The frontend is a two-page
  React SPA (Dashboard + Violation Detail).

  ## Key paths
  - Backend source    :  backend/src/tad/
  - Frontend source   :  frontend/src/
  - Tests             :  backend/tests/, frontend/tests/
  - ADRs              :  docs/decisions/
  - Algorithm params  :  configs/algo_params/
  - Calibration       :  configs/calibration/
  - Eval dataset      :  data/eval/ (LOCKED)

  ## Pinned versions
  - Python            :  3.11.x
  - opencv-python     :  4.10.x
  - FastAPI           :  0.115.x
  - React             :  18.3.x
  - Vite              :  5.4.x
  - Tailwind CSS      :  3.4.x
  - Recharts          :  2.12.x
  - React Router DOM  :  6.26.x

  ## Routes
  - /home                      -> Dashboard
  - /home/details/:id          -> Violation Detail

  ## Status terminology
  - Backend: PASS / REVIEW / FAIL / ERROR
  - UI:      Okay / Somewhat Okay / Not Okay / Error
  - Camera:  L -> "Cam1"   R -> "Cam2"
  - chassis_no -> "Product ID" in the UI

  ## Run commands
  - make test         :  ruff + mypy + pytest (backend)
  - make eval         :  run the locked eval harness
  - make serve        :  run the FastAPI app on :8000
  - make dev-ui       :  run Vite dev server on :5173
  - make build        :  build the full Docker image (backend + UI)

  ## Conventions
  - Type hints on every public Python function.
  - Pydantic models at all API boundaries.
  - No production code in notebooks/.
  - Algorithm parameters live in YAML.
  - UI status/camera mapping is centralised in src/labels.ts.
  - Never hard-code status strings in UI components.



================================================================================
  27. APPENDIX C — ADR TEMPLATE
================================================================================

  # ADR-00N — <title>

  Status      :  Proposed | Accepted | Superseded by ADR-00M
  Date        :  YYYY-MM-DD
  Deciders    :  <names/roles>

  ## Context
  <What is the forcing function? What problem are we solving?>

  ## Decision
  <What did we choose, stated in one or two sentences?>

  ## Alternatives considered
  - <alt 1> — why not
  - <alt 2> — why not
  - <alt 3> — why not

  ## Consequences
  - Positive: <...>
  - Negative: <...>
  - Neutral / follow-up work: <...>

  ## References
  - <link to TRD section, PR, benchmark, etc.>


================================================================================
                          END OF DOCUMENT — TRD v2.1
================================================================================


## Architecture

### High-level architecture (from architecture.txt)

================================================================================
                                                                                
                      END-TO-END SYSTEM ARCHITECTURE                            
                                                                                
                        TRAILING ARM DETECTION                                  
              Developer Implementation Guide (build from zero)                  
                                                                                
================================================================================

  AUDIENCE      :  A developer (or small team) building this system from
                   scratch. Assumes Python, FastAPI, and OpenCV literacy.
  COMPANIONS    :  Use Case Document UC-TAD-001  |  TRD v2.0  |  PRD v1.0
  VERSION       :  1.0  (Draft)
  READING ORDER :  Sections 1 -> 4 first (the mental model), then 5 -> 13
                   as you actually implement, then 14 -> 17 as you harden.



================================================================================
  HOW TO READ THIS DOCUMENT
================================================================================

  This is an architecture-first build guide. It tells you:

     - what components exist
     - what each component owns
     - how components talk to each other
     - what the interfaces look like in code
     - the order to implement them
     - how to test and deploy each piece

  It does NOT re-state the TRD's requirements or SLAs. When in doubt,
  the TRD is authoritative on "what must be true", this document is
  authoritative on "how to build it".

  Every code sketch in this document is illustrative — production code
  will have more error handling, logging, and tests. Use the sketches
  to anchor your mental model, not as copy-paste.

  FOR VISUAL FLOW DIAGRAMS see `docs/architecture_diagram.md`, which
  has Mermaid-rendered system-level, sequence, state-machine, and
  ER diagrams for every flow mentioned here, plus the demo-mode
  replay path that isn't covered below.

  WHAT CHANGED SINCE THE FIRST DRAFT (tracked in ADRs):
    - algo-1.3.0 replaced the RANSAC pipeline with contour + masked
      Hough (ADR-008). Sections 5.6 and 17 in this doc reflect the
      new stages.
    - Phase 4 landed the backend end-to-end, Phase 5 the React UI.
      The directory tree in Section 8 matches what is on disk today.
    - Demo infrastructure (ADR-009): `scripts/run_demo.py`,
      `scripts/seed_demo.py`, `scripts/annotate_v2.py`, and
      `/v1/demo/replay/*` endpoints let anyone boot the whole stack
      locally without Docker. Production wiring
      (`tad.main:app` + `make up` + `make serve`) is unchanged.



+------------------------------------------------------------------------------+
|                            TABLE OF CONTENTS                                 |
+------------------------------------------------------------------------------+

   1.  System at a Glance
   2.  Tech Stack
   3.  Component Architecture
   4.  Runtime Model (Processes, Threads, Async)
   5.  Component Deep Dives
         5.1  Configuration Layer
         5.2  Persistence Layer
         5.3  Calibration Loader
         5.4  Filename Parser
         5.5  Image Validator
         5.6  Measurement Engine (the CV pipeline)
         5.7  Chassis Aggregator
         5.8  Folder Watchers
         5.9  Session Manager
         5.10 API Layer (FastAPI)
         5.11 SSE Event Broker
   6.  Data Flow Sequences
   7.  Database Schema (SQL DDL)
   8.  Directory Structure
   9.  Key Interfaces (Python Signatures)
  10.  Configuration File Formats
  11.  Local Development Setup
  12.  Implementation Roadmap (build order)
  13.  Testing Strategy (per component)
  14.  Deployment Architecture
  15.  Observability and Operational Runbook
  16.  Cross-Cutting Concerns
  17.  Appendix — Code Sketches for Tricky Bits



================================================================================
  1. SYSTEM AT A GLANCE
================================================================================

  The system is a single Python service — one Docker container — that
  exposes a FastAPI HTTP interface and owns two background tasks per
  active session (one folder watcher per camera). Everything runs in a
  single process; concurrency is handled by asyncio plus a small thread
  pool for CPU-bound CV work.

  There are four external systems the service talks to:

      - Frontend / Dashboard  (HTTP + Server-Sent Events)
      - Two image folders     (shared filesystem, read-only)
      - Postgres              (structured records)
      - MinIO (S3-compatible) (debug image blobs)


  +----------------------------------------------------------------------+
  |                     SYSTEM AT A GLANCE                               |
  +----------------------------------------------------------------------+

          +-------------------+                +-------------------+
          |  Frontend / UI    |                |  Capture System   |
          |  (browser on      |                |  (writes images   |
          |  station tablet)  |                |   to folders)     |
          +---------+---------+                +---------+---------+
                    |                                    |
                    |  HTTP + SSE                        |  filesystem
                    v                                    v
          +---------------------------------------------------------+
          |                      CV Service                         |
          |                                                         |
          |    +------------+   +----------------+   +-----------+  |
          |    | API Layer  |-->| Session Mgr    |-->| Folder    |  |
          |    | (FastAPI)  |   |                |   | Watchers  |  |
          |    +------------+   +--------+-------+   +-----+-----+  |
          |          ^                   |                 |        |
          |          |                   v                 v        |
          |    +-----+------+    +---------------+   +-----------+  |
          |    | SSE Broker |<---| Aggregator    |<--| Pipeline  |  |
          |    +------------+    +---------------+   +-----------+  |
          |                              |                 |        |
          |                              v                 v        |
          |                        +---------------------------+    |
          |                        |    Persistence Layer      |    |
          |                        +---------------------------+    |
          +---------------------------------------------------------+
                               |                 |
                               v                 v
                       +--------------+   +-------------+
                       |  Postgres    |   |  MinIO      |
                       |  (records)   |   |  (blobs)    |
                       +--------------+   +-------------+


  THE MENTAL MODEL IN ONE SENTENCE
  --------------------------------
     When Start is called, two folder watchers spin up; each image they
     find flows through a deterministic CV pipeline, the result is
     saved, and an event is pushed to every connected dashboard — in
     parallel, the aggregator is listening for matched L/R pairs and
     emits a second event per chassis.



================================================================================
  2. TECH STACK
================================================================================

  LANGUAGE AND RUNTIME
     Python 3.11.x           Runtime. 3.12 is fine; 3.10 is acceptable
                             fallback. Type hints used everywhere.

  WEB / API
     FastAPI 0.115.x         HTTP framework. ASGI-native. Pydantic
                             models define every boundary.
     Uvicorn 0.32.x          ASGI server. Single worker process per
                             container — session state lives in-memory
                             and must not be sharded yet.
     sse-starlette 2.1.x     Server-Sent Events helper, integrates
                             cleanly with FastAPI's async routes.

  COMPUTER VISION
     opencv-python 4.10.x    Classical primitives used by the pipeline:
                             cv2.GaussianBlur, cv2.adaptiveThreshold,
                             cv2.morphologyEx, cv2.findContours,
                             cv2.HoughCircles (see ADR-008).
     numpy 1.26.x            Arrays and mask arithmetic.
     scikit-image 0.24.x     (Retained as an optional helper; no longer
                             on the critical path.)

  FILESYSTEM WATCHING
     watchdog 5.0.x          Cross-platform file-system events. On
                             Linux it uses inotify; on the plant
                             server this is what we will rely on.

  PERSISTENCE
     SQLAlchemy 2.0.x        ORM and Core. Async engine.
     psycopg[binary] 3.2.x   Postgres driver.
     Alembic                 Migrations.
     minio 7.2.x             Blob storage client for MinIO / S3.

  CONFIG AND SCHEMA
     Pydantic 2.9.x          Pydantic Settings for env, Pydantic models
                             for API and config schemas.
     PyYAML 6.0.x            Loading algo_params and calibration YAML.

  TEST / QUALITY
     pytest 8.3.x            Tests.
     pytest-asyncio          Async test support.
     pytest-cov 5.0.x        Coverage gate.
     hypothesis              Property-based tests for the CV pipeline.
     ruff 0.7.x              Lint + formatter.
     mypy 1.13.x             Static typing.
     pre-commit              Git hooks.

  PACKAGING / INFRA
     Docker + Compose        Single image; docker-compose for local
                             dev stack (Postgres + MinIO).
     Make                    Stable entrypoints: make test / eval /
                             serve / lint / format.

  OBSERVABILITY
     structlog               Structured JSON logs.
     prometheus-client       /metrics endpoint.
     opentelemetry (P1)      Traces — add once core is stable.



================================================================================
  3. COMPONENT ARCHITECTURE
================================================================================

  The service is structured as eleven internal components. Each has a
  single responsibility; the arrow direction shows "depends on".

  +----------------------------------------------------------------------+
  |                     COMPONENT DEPENDENCY GRAPH                       |
  +----------------------------------------------------------------------+

         API Layer (FastAPI routes)
                |
                v
         Session Manager   <-------------------+
          |    |    |                          |
          v    v    v                          |
     Folder    SSE    Aggregator               |
     Watchers  Broker     |                    |
          |               |                    |
          v               v                    |
     Measurement Engine   |                    |
          |               |                    |
     +----+----+----+     |                    |
     |         |    |     |                    |
     v         v    v     |                    |
  Filename  Image  Calib  |                    |
  Parser    Valid  Loader |                    |
                          v                    |
                    Persistence Layer ---------+
                    (Postgres + MinIO)

              Configuration Layer
              (read by everything above at startup)


  WHY THIS SHAPE
     - API is thin; it delegates to Session Manager for anything stateful.
     - Session Manager owns the session lifecycle and holds references
       to the per-session watchers, aggregator, and event stream.
     - The Measurement Engine is PURE — it takes an image and returns a
       result. It does not know about sessions, databases, or the API.
     - Persistence is the only place that writes to Postgres / MinIO.
       Everything else hands records to it.
     - Configuration is read once at startup and treated as immutable
       for the lifetime of the process.



================================================================================
  4. RUNTIME MODEL (PROCESSES, THREADS, ASYNC)
================================================================================

  ONE PROCESS, ONE EVENT LOOP, ONE SMALL THREADPOOL
  -------------------------------------------------

     - The service is a single Uvicorn process. Session state lives in
       a module-level dict keyed by session_id. Do NOT add extra
       Uvicorn workers — that would split session state across
       processes and break the aggregator.

     - Async I/O (HTTP handlers, DB writes, MinIO uploads, SSE pushes)
       all run on the default asyncio event loop.

     - CPU-bound work (OpenCV operations, RANSAC) runs in a bounded
       thread pool (concurrent.futures.ThreadPoolExecutor) scheduled
       from the event loop via asyncio.to_thread. OpenCV releases the
       GIL during most of its operations, so true parallelism is
       achievable.

     - The watchdog observer runs its own internal thread(s). Events
       are pushed into an asyncio.Queue using
       loop.call_soon_threadsafe, so the event loop consumes them
       without blocking.


  CONCURRENCY BOUNDARIES

     - ONE folder watcher per camera side per active session.
     - ONE aggregator task per active session.
     - ONE SSE subscriber queue per connected dashboard client per
       session.
     - N image-processing tasks running in parallel, bounded by the
       thread pool size (default: 2 * CPU cores).


  BACK-PRESSURE

     If images pile up faster than the pipeline can drain them, the
     asyncio.Queue between the watcher and the pipeline grows.
     The queue has a configurable max size. When it is full, new
     filesystem events are dropped into a "deferred" queue and a
     warning event is emitted to the SSE stream. This is defensive;
     in practice the pipeline is far faster than the capture cadence.



================================================================================
  5. COMPONENT DEEP DIVES
================================================================================


--------------------------------------------------------------------------------
  5.1  CONFIGURATION LAYER
--------------------------------------------------------------------------------

  PURPOSE
     Load and validate all configuration at startup. Make it easy to
     test with overrides. Surface a single, typed Settings object.

  SOURCES (in precedence order, first wins)
     1. Environment variables  (e.g. DB_DSN, IMAGES_LEFT_DIR)
     2. .env file              (only in local dev)
     3. configs/algo_params/<version>.yaml
     4. configs/calibration/<id>.yaml

  IMPLEMENTATION
     - One Pydantic Settings class for env.
     - One Pydantic model per YAML file (AlgoParams, Calibration).
     - A get_settings() function with functools.lru_cache so every
       caller gets the same instance.

  SKETCH
     # src/tad/config/settings.py
     from pydantic_settings import BaseSettings

     class Settings(BaseSettings):
         db_dsn: str
         minio_endpoint: str
         minio_access_key: str
         minio_secret_key: str
         images_left_dir: str
         images_right_dir: str
         algo_params_version: str
         default_calibration_left: str
         default_calibration_right: str
         asymmetry_threshold_mm: float = 0.15
         queue_max_size: int = 256

         class Config:
             env_file = ".env"

     @functools.lru_cache
     def get_settings() -> Settings:
         return Settings()


--------------------------------------------------------------------------------
  5.2  PERSISTENCE LAYER
--------------------------------------------------------------------------------

  PURPOSE
     The ONLY component that writes to Postgres or MinIO. Exposes a
     Repository class per aggregate (Session, Measurement, Chassis).
     Uses SQLAlchemy 2.x async engine.

  WHY REPOSITORY PATTERN
     - Testability: stub a repository instead of a real DB.
     - Clear ownership: no SQL lives in the aggregator or the pipeline.
     - Transaction control: the API layer opens a session, repositories
       accept it.

  TABLES
     sessions, measurements, chassis_records, calibrations
     (full DDL in Section 7)

  KEY METHODS

     class SessionRepository:
         async def create(self, record: Session) -> Session
         async def mark_stopped(self, id: UUID, summary: dict) -> None
         async def get(self, id: UUID) -> Session | None

     class MeasurementRepository:
         async def insert(self, record: Measurement) -> Measurement
         async def get(self, id: UUID) -> Measurement | None
         async def list_by_session(self, sid: UUID) -> list[Measurement]
         async def get_pair(self, sid: UUID, chassis_no: str) ->
             tuple[Measurement | None, Measurement | None]   # (L, R)

     class ChassisRepository:
         async def upsert(self, record: ChassisRecord) -> ChassisRecord
         async def search_by_no(self, chassis_no: str)
             -> list[ChassisRecord]

  BLOB STORAGE
     class DebugImageStore:
         def put(self, key: str, jpeg_bytes: bytes) -> str   # returns URL
         def get_url(self, key: str) -> str

     Keys are of the form:
         sessions/<session_id>/measurements/<measurement_id>.jpg


--------------------------------------------------------------------------------
  5.3  CALIBRATION LOADER
--------------------------------------------------------------------------------

  PURPOSE
     Load the active calibration for each camera side and expose
     mm_per_px when the pipeline asks for it.

  CONTRACT
     class CalibrationLoader:
         def get(self, camera_side: Literal["L", "R"]) -> Calibration

     Calibration is a Pydantic model:
         calibration_id: str
         camera_side: Literal["L", "R"]
         mm_per_px: float
         method: str
         valid_from: datetime
         operator: str
         reference_image: str

  STARTUP BEHAVIOUR
     - Reads the two default calibration files named in Settings.
     - Validates both parse and have camera_side matching the filename.
     - If either is missing / invalid, /ready returns 503 and
     /sessions/start refuses with ERR_NO_CALIBRATION.


--------------------------------------------------------------------------------
  5.4  FILENAME PARSER
--------------------------------------------------------------------------------

  PURPOSE
     Convert a filename into a (chassis_no, camera_side) pair or a
     clear rejection.

  CONTRACT
     FILENAME_RE = re.compile(
         r"^(?P<chassis_no>[A-HJ-NPR-Z0-9]{17})"
         r"_(?P<camera>[LR])"
         r"(?:_\d+)?"
         r"\.(?:jpg|jpeg|png)$",
         re.IGNORECASE,
     )

     @dataclass(frozen=True)
     class ParsedName:
         chassis_no: str
         camera_side: Literal["L", "R"]

     def parse_filename(name: str) -> ParsedName:
         m = FILENAME_RE.match(name)
         if not m:
             raise BadFilename(f"filename does not match convention: {name}")
         return ParsedName(
             chassis_no=m["chassis_no"].upper(),
             camera_side=m["camera"].upper(),
         )

  NOTE
     The parser is pure and synchronous. Trivial to unit-test.


--------------------------------------------------------------------------------
  5.5  IMAGE VALIDATOR
--------------------------------------------------------------------------------

  PURPOSE
     Gate every image against the Image Contract in TRD Section 5.1
     before the pipeline sees it.

  CHECKS
     - File is a non-empty, complete JPEG or PNG (trailing bytes OK).
     - Resolution within configured min / max.
     - Colour space is 3-channel RGB.
     - Laplacian-variance blur metric >= 100.
     - Mean pixel value within [40, 220].

  CONTRACT
     class ValidationResult:
         ok: bool
         error_code: str | None
         message: str | None
         meta: dict               # resolution, blur metric, exposure

     def validate(image_bytes: bytes) -> tuple[np.ndarray, ValidationResult]

     If ok is False, meta still contains whatever was measurable; the
     caller persists an ERROR measurement with the error_code.


--------------------------------------------------------------------------------
  5.6  MEASUREMENT ENGINE — THE CV PIPELINE
--------------------------------------------------------------------------------

  PURPOSE
     The heart of the system. Given an image and a calibration, return
     a MeasurementResult. PURE — no I/O, no database, no logging beyond
     debug traces.

  INPUTS / OUTPUTS
     @dataclass
     class PipelineInput:
         image_bgr: np.ndarray     # OpenCV convention
         calibration: Calibration
         algo_params: AlgoParams

     @dataclass
     class PipelineOutput:
         diameter_mm: float | None
         status: Literal["PASS", "FAIL", "REVIEW", "ERROR"]
         confidence: float | None
         circle: tuple[int, int, float] | None   # (cx, cy, r_px)
         error_code: str | None
         annotated_image: np.ndarray            # always produced

  ORCHESTRATION
     measure_innermost_diameter(inp: PipelineInput) -> PipelineOutput

     Breaks down into named stages (each in its own file under
     measurement/):

        preprocessing.py   -> gaussian_blur()
        threshold.py       -> adaptive_threshold() + morph_close()
        contour_detect.py  -> find_candidate_contours()
                               + detect_circle_in_contour()
                               + detect_circle()
        confidence.py      -> compute_confidence() + evaluate_status()
        annotate.py        -> render_debug_image()
        pipeline.py        -> orchestrates the above
        models.py          -> PipelineInput, PipelineOutput, InnerCircle

  CONCRETE SKETCH (pipeline.py, algo-1.3.0)

     def measure_innermost_diameter(inp: PipelineInput) -> PipelineOutput:
         gray    = cv2.cvtColor(inp.image_bgr, cv2.COLOR_BGR2GRAY)
         blurred = gaussian_blur(gray, inp.blur_kernel)

         binary  = adaptive_threshold(blurred,
                     block_size=inp.threshold_block_size,
                     c=inp.threshold_c)
         cleaned = morph_close(binary,
                     kernel_size=inp.morph_kernel_size,
                     iterations=inp.morph_iterations)

         circle = detect_circle(
             gray, cleaned,
             mm_per_px=inp.calibration_mm_per_px,
             target_diameter_mm=inp.target_diameter_mm,
             radius_tolerance_mm=inp.radius_tolerance_mm,
             min_contour_area=inp.contour_min_area,
             dp=inp.hough_dp, min_dist=inp.hough_min_dist,
             param1=inp.hough_param1, param2=inp.hough_param2)

         if circle is None:
             return _error(inp, "ERR_NO_CIRCLE",
                 "no circle matching target radius")

         diameter_mm = 2.0 * circle.radius_px * inp.calibration_mm_per_px
         status = evaluate_status(
             diameter_mm, inp.target_diameter_mm,
             ok_band_mm=inp.ok_band_mm,
             somewhat_ok_band_mm=inp.somewhat_ok_band_mm,
             tolerance_min_mm=inp.tolerance_min_mm,
             tolerance_max_mm=inp.tolerance_max_mm)
         conf = compute_confidence(
             diameter_mm, inp.target_diameter_mm,
             somewhat_ok_band_mm=inp.somewhat_ok_band_mm)

         annotated = render_debug_image(
             inp.image_bgr, circle, diameter_mm, status, conf,
             target_diameter_mm=inp.target_diameter_mm,
             mm_per_px=inp.calibration_mm_per_px)

         return PipelineOutput(
             diameter_mm=diameter_mm,
             status=status,
             confidence=conf,
             circle=(circle.cx, circle.cy, circle.radius_px),
             error_code=None,
             annotated_image=annotated,
         )

  DETERMINISM
     The contour + masked Hough pipeline is fully deterministic: there
     is no stochastic sampling (RANSAC has been removed).  Given the
     same image + algo_params + calibration, the output is identical.

  TESTING
     - Synthetic fixtures (bright plate + dark circle) committed under
       tests/fixtures/images/ drive the unit tests.
     - Real assembly-line images (cam18jdleofhtlhj6_{L,R}.jpg) serve as
       a smoke-test fixture for the end-to-end pipeline.
     - See ADR-008 for the rationale behind switching away from the
       earlier Canny + pick_innermost + RANSAC approach.


--------------------------------------------------------------------------------
  5.7  CHASSIS AGGREGATOR
--------------------------------------------------------------------------------

  PURPOSE
     Joins per-camera results into per-chassis results. One instance
     per active session. Holds a small in-memory map:

         pending: dict[str, dict[Literal["L", "R"], Measurement]]

     chassis_no -> {"L": ..., "R": ...}  with missing side absent.

  CONTRACT
     class Aggregator:
         def __init__(self, session_id, event_publisher,
                      chassis_repo, asymmetry_threshold_mm): ...

         async def accept(self, measurement: Measurement) -> None:
             """Called once per per-camera result."""

         async def flush(self) -> list[ChassisRecord]:
             """Called on session stop; emits REVIEW records for
             any chassis_no with a missing side."""

  BEHAVIOUR
     1. On accept(L or R):
        - insert into pending[chassis_no][side]
        - if both sides now present:
            compute ChassisRecord (status matrix + asymmetry)
            persist via chassis_repo.upsert
            publish chassis_result event
            pop pending[chassis_no]
     2. On flush():
        - iterate remaining pending entries
        - build ChassisRecord with missing side nulls, status=REVIEW,
          reason "missing side: L" or "missing side: R"
        - persist + publish
        - clear pending

  CONCURRENCY
     The aggregator is called from the pipeline's completion callback,
     which runs on the event loop. One asyncio.Lock guards pending.


--------------------------------------------------------------------------------
  5.8  FOLDER WATCHERS
--------------------------------------------------------------------------------

  PURPOSE
     Detect new files in /images/left and /images/right and push them
     into a processing queue. One watcher per side per active session.

  IMPLEMENTATION NOTES
     - Use watchdog.observers.Observer with a FileSystemEventHandler.
     - On on_created(event): enqueue the path.
     - On_modified: ignore (create is what we want).
     - The watchdog thread is not the event loop; use
       loop.call_soon_threadsafe(queue.put_nowait, path).

  SAFE-READ PROTOCOL
     Images may be visible in the filesystem before the writer finishes
     flushing. The processor, NOT the watcher, verifies stability:

        1. Record the file's size.
        2. Sleep a short configured interval.
        3. Check size again. If changed, loop.
        4. If unchanged for N iterations, proceed.

     This avoids partial-JPEG failures without requiring the capture
     system to signal completion.

  CONTRACT
     class FolderWatcher:
         def __init__(self, side: Literal["L", "R"], path: Path,
                      queue: asyncio.Queue[Path]): ...
         def start(self) -> None
         def stop(self) -> None


--------------------------------------------------------------------------------
  5.9  SESSION MANAGER
--------------------------------------------------------------------------------

  PURPOSE
     The orchestration layer. Creates sessions, spins up the watchers
     and aggregator, consumes images from the queue, and shuts it all
     down on stop.

  STATE
     class SessionManager:
         active: dict[UUID, SessionRuntime]

         class SessionRuntime:
             session: SessionRecord           # persisted row
             queue: asyncio.Queue[QueueItem]
             watcher_l: FolderWatcher
             watcher_r: FolderWatcher
             aggregator: Aggregator
             event_broker: SseBroker          # per-session fan-out
             consumer_task: asyncio.Task
             algo_params: AlgoParams

  START FLOW
     1. Validate calibrations and folders exist.
     2. INSERT into sessions table; get UUID.
     3. Build queue, watchers, aggregator, broker.
     4. Spawn consumer_task: loops reading queue, calls process_item.
     5. Store runtime in active[session_id].
     6. Return SessionStartResponse.

  STOP FLOW
     1. Stop watchers (no more new items).
     2. Drain queue by waiting for consumer task to finish in-flight
        work, bounded by a timeout.
     3. Aggregator.flush() — emits REVIEW records for any orphan.
     4. Compute summary; update sessions row.
     5. Close the SSE broker (all subscribers disconnect cleanly).
     6. Remove from active.

  PROCESS_ITEM
     Called once per image pulled from the queue:

        1. Wait for file-size stability (safe-read protocol).
        2. Read bytes; validate; decode via OpenCV.
        3. Parse filename (camera side, chassis_no).
        4. Load calibration for that side.
        5. Run pipeline (CPU-bound, via asyncio.to_thread).
        6. Upload debug image to MinIO.
        7. Insert Measurement row (via repository).
        8. Publish camera_result event to SSE broker.
        9. aggregator.accept(measurement).


--------------------------------------------------------------------------------
  5.10  API LAYER (FastAPI)
--------------------------------------------------------------------------------

  PURPOSE
     Thin HTTP surface. Delegates to Session Manager and repositories.
     Validates request/response via Pydantic.

  ROUTE SUMMARY

     POST   /v1/sessions/start
     POST   /v1/sessions/{id}/stop
     GET    /v1/sessions/{id}/events          (SSE)
     GET    /v1/sessions/{id}/results         (polling fallback)
     GET    /v1/measurements/{id}
     GET    /v1/debug/{id}                    (proxies a MinIO stream)
     GET    /v1/health                        (liveness)
     GET    /v1/ready                         (readiness)
     GET    /metrics                          (Prometheus)

  DEPENDENCIES
     Each route declares its dependencies via FastAPI's Depends():

        async def route(
            session_manager: SessionManager = Depends(get_session_manager),
            measurement_repo: MeasurementRepository = Depends(...),
        ): ...

     This makes swapping in fakes for tests trivial.

  ERROR HANDLING
     Custom exceptions (NoCalibrationError, SessionNotActiveError, etc.)
     are mapped to error codes via a FastAPI exception handler. No
     stack traces ever reach the client.


--------------------------------------------------------------------------------
  5.11  SSE EVENT BROKER
--------------------------------------------------------------------------------

  PURPOSE
     In-memory fan-out of session events to every connected dashboard.
     Per-session isolation: one broker per session.

  MODEL
     class SseBroker:
         subscribers: list[asyncio.Queue[Event]]

         def subscribe(self) -> asyncio.Queue[Event]:
             q = asyncio.Queue(maxsize=128)
             self.subscribers.append(q)
             return q

         def unsubscribe(self, q: asyncio.Queue) -> None: ...

         async def publish(self, event: Event) -> None:
             for q in list(self.subscribers):
                 try:
                     q.put_nowait(event)
                 except asyncio.QueueFull:
                     # slow client; drop the client rather than
                     # backpressure the producer
                     self.unsubscribe(q)

  DELIVERY
     FastAPI route:

        @router.get("/v1/sessions/{sid}/events")
        async def events(sid: UUID, sm: SessionManager = ...):
            runtime = sm.require_active(sid)
            queue = runtime.event_broker.subscribe()
            return EventSourceResponse(_stream(queue, runtime))

        async def _stream(q, runtime):
            try:
                while True:
                    event = await q.get()
                    yield {"event": event.type, "data": event.json()}
            finally:
                runtime.event_broker.unsubscribe(q)

  EVENT TYPES
     session_opened
     camera_result
     chassis_result
     warning
     session_closed

  RESILIENCE
     Events are IN-MEMORY only — dropping a client does not lose data,
     because every event is persisted to Postgres at the moment of
     publish. A reconnecting client can /results?since=cursor to catch
     up, then re-subscribe.



================================================================================
  6. DATA FLOW SEQUENCES
================================================================================


  6.1  SEQUENCE — SESSION START
  -----------------------------

     Frontend                 API              SessionMgr     Persistence
        |                      |                    |              |
        |-- POST /start ------>|                    |              |
        |                      |-- create() ------->|              |
        |                      |                    |-- INSERT --->|
        |                      |                    |<-- row ------|
        |                      |                    |
        |                      |                    |-- start watchers
        |                      |                    |-- spawn consumer
        |                      |                    |-- init broker
        |                      |<-- SessionRuntime -|
        |<-- 201 SessionResp --|                    |
        |                                           |
        |-- GET /events (SSE) ------------------->(subscribes to broker)
        |<== session_opened event ================|


  6.2  SEQUENCE — IMAGE ARRIVES AND IS PROCESSED
  ----------------------------------------------

     Watcher   Queue   Consumer   Pipeline   Persistence   Broker   Aggregator
        |       |         |          |           |          |           |
   (new file)   |         |          |           |          |           |
        |-push->|         |          |           |          |           |
        |       |--pop--->|          |           |          |           |
        |       |         |-validate + parse --> |          |           |
        |       |         |-to_thread-> measure()|          |           |
        |       |         |<-----PipelineOutput--|          |           |
        |       |         |-put debug image ---->|          |           |
        |       |         |                      |-MinIO--->|           |
        |       |         |-insert Measurement ->|          |           |
        |       |         |                      |          |           |
        |       |         |-publish camera_result ---------->|          |
        |       |         |-aggregator.accept() ------------>|--------->|
        |       |                                             |         |
        |       |                             if pair complete|         |
        |       |                             chassis_result<-|         |
        |       |                             published       |         |


  6.3  SEQUENCE — SESSION STOP
  ----------------------------

     Frontend                 API              SessionMgr   Aggregator    DB
        |                      |                    |           |         |
        |-- POST /stop ------->|                    |           |         |
        |                      |-- stop() --------->|           |         |
        |                      |                    |-- stop watchers     |
        |                      |                    |-- await consumer    |
        |                      |                    |-- flush ->|         |
        |                      |                    |           |-upsert->|
        |                      |                    |<- orphans -|        |
        |                      |                    |-- compute summary   |
        |                      |                    |-- UPDATE sessions->>|
        |                      |                    |-- close broker      |
        |                      |<-- SessionSummary -|                     |
        |<-- 200 Summary ------|                    |                     |



================================================================================
  7. DATABASE SCHEMA (SQL DDL)
================================================================================

  The schema uses Postgres types. UUIDs are generated client-side for
  idempotency friendliness. Timestamps are TIMESTAMPTZ.


  -- sessions ----------------------------------------------------------
  CREATE TABLE sessions (
      session_id           UUID         PRIMARY KEY,
      started_at           TIMESTAMPTZ  NOT NULL,
      stopped_at           TIMESTAMPTZ,
      started_by           VARCHAR(64)  NOT NULL,
      status               VARCHAR(16)  NOT NULL
                                       CHECK (status IN
                                           ('ACTIVE', 'STOPPED', 'FAILED')),
      left_dir             TEXT         NOT NULL,
      right_dir            TEXT         NOT NULL,
      algo_params_version  VARCHAR(32)  NOT NULL,
      notes                TEXT,
      summary_json         JSONB        -- populated at stop
  );

  CREATE INDEX ix_sessions_started_at ON sessions (started_at DESC);


  -- measurements -------------------------------------------------------
  CREATE TABLE measurements (
      measurement_id       UUID         PRIMARY KEY,
      session_id           UUID         NOT NULL REFERENCES sessions,
      chassis_no           VARCHAR(17)  NOT NULL,
      camera_side          CHAR(1)      NOT NULL
                                       CHECK (camera_side IN ('L', 'R')),
      image_path           TEXT         NOT NULL,
      diameter_mm          NUMERIC(6,3),
      tolerance_min_mm     NUMERIC(6,3) NOT NULL,
      tolerance_max_mm     NUMERIC(6,3) NOT NULL,
      status               VARCHAR(16)  NOT NULL
                                       CHECK (status IN
                                           ('PASS', 'FAIL',
                                            'REVIEW', 'ERROR')),
      confidence_score     NUMERIC(4,3),
      circle_center_x_px   INTEGER,
      circle_center_y_px   INTEGER,
      radius_px            NUMERIC(8,3),
      mm_per_px            NUMERIC(8,6) NOT NULL,
      calibration_version  VARCHAR(32)  NOT NULL,
      algo_params_version  VARCHAR(32)  NOT NULL,
      debug_image_key      TEXT,
      error_code           VARCHAR(32),
      error_message        TEXT,
      processed_at         TIMESTAMPTZ  NOT NULL,
      latency_ms           INTEGER      NOT NULL
  );

  CREATE INDEX ix_measurements_session_chassis
      ON measurements (session_id, chassis_no);
  CREATE INDEX ix_measurements_chassis_no
      ON measurements (chassis_no);
  CREATE INDEX ix_measurements_processed_at
      ON measurements (processed_at DESC);


  -- chassis_records ----------------------------------------------------
  CREATE TABLE chassis_records (
      chassis_record_id    UUID         PRIMARY KEY,
      session_id           UUID         NOT NULL REFERENCES sessions,
      chassis_no           VARCHAR(17)  NOT NULL,
      left_measurement_id  UUID         REFERENCES measurements,
      right_measurement_id UUID         REFERENCES measurements,
      left_diameter_mm     NUMERIC(6,3),
      right_diameter_mm    NUMERIC(6,3),
      avg_diameter_mm      NUMERIC(6,3),
      asymmetry_mm         NUMERIC(6,3),
      overall_status       VARCHAR(16)  NOT NULL,
      reason               TEXT,         -- e.g. "missing side: L"
      aggregated_at        TIMESTAMPTZ  NOT NULL,
      CONSTRAINT uq_session_chassis
          UNIQUE (session_id, chassis_no)
  );

  CREATE INDEX ix_chassis_records_chassis_no
      ON chassis_records (chassis_no);


  -- calibrations (source of truth is the YAML; table is for audit) ----
  CREATE TABLE calibrations (
      calibration_id       VARCHAR(32)  PRIMARY KEY,
      camera_side          CHAR(1)      NOT NULL CHECK (camera_side IN ('L','R')),
      mm_per_px            NUMERIC(8,6) NOT NULL,
      method               VARCHAR(32)  NOT NULL,
      valid_from           TIMESTAMPTZ  NOT NULL,
      operator             VARCHAR(64)  NOT NULL,
      reference_image      TEXT,
      imported_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
  );



================================================================================
  8. DIRECTORY STRUCTURE
================================================================================

  trailing-arm-detection/                      (as-built after Phase 5)
  |-- CLAUDE.md                                 (project memory file)
  |-- PLAN.md                                   (phase roadmap)
  |-- pyproject.toml
  |-- .pre-commit-config.yaml
  |-- .env.example
  |-- alembic.ini
  |-- Makefile                                  (make demo, demo-seed,
  |                                              dev-ui, test-ui, etc.)
  |-- Dockerfile                                (multi-stage, node 20 -> py3.11)
  |-- docker-compose.yml                        (Postgres + MinIO)
  |
  |-- configs/
  |   |-- algo_params/
  |   |   |-- algo-1.3.0.yaml                  (current; see ADR-008)
  |   |-- calibration/
  |       |-- cal-2026-03-14-L.yaml
  |       |-- cal-2026-03-14-R.yaml
  |
  |-- src/tad/
  |   |-- __init__.py
  |   |-- main.py                               (uvicorn entrypoint; SQL +
  |   |                                          MinIO wiring via create_app)
  |   |-- config/
  |   |   |-- settings.py                       (Pydantic Settings)
  |   |   |-- algo_params.py                    (ThresholdParams,
  |   |   |                                      MorphologyParams, etc.)
  |   |   |-- calibration.py
  |   |-- api/
  |   |   |-- app.py                            (create_app factory)
  |   |   |-- deps.py                           (Depends() wiring)
  |   |   |-- middleware.py                     (RequestIdMiddleware)
  |   |   |-- errors.py                         (TadError hierarchy
  |   |   |                                      + exception handlers)
  |   |   |-- schemas.py                        (every Pydantic request
  |   |   |                                      + response + SSE event)
  |   |   |-- routes_sessions.py                (start / stop / events (SSE)
  |   |   |                                      / results / list)
  |   |   |-- routes_chassis.py                 (list / detail / decision
  |   |   |                                      / flag)
  |   |   |-- routes_dashboard.py               (GET /v1/dashboard/summary)
  |   |   |-- routes_measurements.py            (GET /v1/measurements/{id}
  |   |   |                                      + /v1/debug/{id})
  |   |   |-- routes_health.py                  (/v1/health + /v1/ready)
  |   |   |-- routes_demo.py                    (/v1/demo/replay/*,
  |   |                                          see ADR-009)
  |   |-- sessions/
  |   |   |-- manager.py                        (SessionManager)
  |   |   |-- runtime.py                        (SessionRuntime dataclass)
  |   |   |-- consumer.py                       (process_item loop)
  |   |   |-- broker.py                         (SseBroker with slow-
  |   |   |                                      subscriber drop)
  |   |   |-- aggregator.py                     (status matrix +
  |   |   |                                      asymmetry downgrade)
  |   |   |-- watcher.py                        (FolderWatcher ->
  |   |                                          asyncio.Queue bridge)
  |   |-- data/
  |   |   |-- filename_parser.py                (VIN regex + ParsedName)
  |   |   |-- image_validator.py                (quality gates)
  |   |   |-- safe_read.py                      (size-stability loop)
  |   |-- measurement/                          (pure CV; see ADR-008)
  |   |   |-- pipeline.py
  |   |   |-- preprocessing.py                  (gaussian_blur)
  |   |   |-- threshold.py                      (adaptive_threshold,
  |   |   |                                      morph_close)
  |   |   |-- contour_detect.py                 (find_candidate_contours,
  |   |   |                                      detect_circle_in_contour,
  |   |   |                                      detect_circle)
  |   |   |-- confidence.py                     (compute_confidence,
  |   |   |                                      evaluate_status)
  |   |   |-- annotate.py
  |   |   |-- models.py                         (PipelineInput/Output,
  |   |   |                                      InnerCircle)
  |   |   |-- __main__.py                       (CLI: `python -m tad.measurement`)
  |   |-- persistence/
  |   |   |-- db.py                             (async engine, session factory)
  |   |   |-- models.py                         (SQLAlchemy ORM +
  |   |   |                                      frozen-dataclass DTOs)
  |   |   |-- repositories.py                   (Protocol + SQL impls)
  |   |   |-- blob_store.py                     (MinIOStore + InMemory fake)
  |   |   |-- migrations/
  |   |       |-- env.py
  |   |       |-- versions/
  |   |           |-- 001_initial_schema.py
  |   |-- observability/
  |       |-- logging_conf.py                   (structlog JSON + hash)
  |
  |-- frontend/                                 (Phase 5 -- React SPA)
  |   |-- package.json
  |   |-- vite.config.ts                        (/v1 proxy + Vitest config)
  |   |-- tailwind.config.ts
  |   |-- tsconfig.json
  |   |-- index.html
  |   |-- README.md                             (how to test the frontend)
  |   |-- src/
  |   |   |-- main.tsx
  |   |   |-- App.tsx                           (BrowserRouter + routes)
  |   |   |-- routes.ts
  |   |   |-- labels.ts                         (status/camera mapping,
  |   |   |                                      TRD 10.3)
  |   |   |-- styles/index.css                  (Tailwind entry)
  |   |   |-- api/
  |   |   |   |-- client.ts                     (axios)
  |   |   |   |-- types.ts                      (mirrors Pydantic schemas)
  |   |   |   |-- dashboard.ts / chassis.ts /
  |   |   |   |   sessions.ts / sse.ts /
  |   |   |   |   demo.ts
  |   |   |-- hooks/
  |   |   |   |-- useLiveSession.ts
  |   |   |   |-- useChassisList.ts
  |   |   |-- pages/
  |   |   |   |-- Dashboard.tsx                 (auto-triggers demo replay)
  |   |   |   |-- ViolationDetail.tsx
  |   |   |-- components/
  |   |       |-- Header.tsx
  |   |       |-- StatusPill.tsx
  |   |       |-- KpiDonut.tsx
  |   |       |-- KpiTrend.tsx
  |   |       |-- AlertsList.tsx
  |   |       |-- FiltersBar.tsx
  |   |       |-- ProductionTable.tsx
  |   |       |-- Pagination.tsx
  |   |       |-- CameraCard.tsx
  |   |       |-- DetailPanel.tsx
  |   |-- tests/
  |       |-- setup.ts
  |       |-- unit/*.test.{ts,tsx}              (27 tests across 7 files)
  |
  |-- tests/
  |   |-- fakes.py                              (InMemory*Repository impls)
  |   |-- unit/
  |   |   |-- test_filename_parser.py
  |   |   |-- test_image_validator.py
  |   |   |-- test_safe_read.py
  |   |   |-- test_pipeline.py + stage tests
  |   |   |-- test_threshold.py
  |   |   |-- test_contour_detect.py
  |   |   |-- test_confidence.py
  |   |   |-- test_aggregator.py
  |   |   |-- test_broker.py
  |   |   |-- test_middleware.py
  |   |   |-- test_settings.py + test_algo_params.py + test_calibration.py
  |   |-- integration/
  |   |   |-- conftest.py
  |   |   |-- test_api_routes.py                (every HTTP route)
  |   |   |-- test_session_flow.py              (full E2E via TestClient)
  |   |-- fixtures/
  |       |-- images/                           (cam18jdleofhtlhj6_{L,R}.jpg
  |       |                                      plus annotated debug files)
  |       |-- test_images/
  |       |   |-- yca_valid/                    (321 L + 321 R real plant
  |       |                                      photos for demo replay)
  |       |-- calibration/
  |
  |-- scripts/
  |   |-- run_demo.py                           (in-memory backend, no Docker)
  |   |-- seed_demo.py                          (synthetic image burst)
  |   |-- test_real_images.py                   (CV-only smoke test)
  |   |-- estimate_real_diameters.py            (diagnostic)
  |   |-- annotate_real_images.py               (make the ADR-008 evidence)
  |   |-- annotate_v2.py                        (algo-1.3.0 annotation)
  |
  |-- docs/
  |   |-- decisions/                            (ADR-001 through ADR-009)
  |   |-- architecture.txt                      (this doc)
  |   |-- architecture_diagram.md               (Mermaid flow diagrams)
  |   |-- demo_walkthrough.md                   (step-by-step local demo)
  |   |-- prd_doc.txt
  |   |-- trd_doc.txt
  |   |-- user_stories.txt
  |   |-- Trailing_Arm_Detection_UseCase.md
  |
  |-- .github/workflows/
  |   |-- ci-backend.yml                        (ruff + mypy + pytest)
  |   |-- ci-frontend.yml                       (eslint + vitest + build)
  |
  |-- notebooks/                                (exploration only)
  |-- data/                                     (.gitignored)



================================================================================
  9. KEY INTERFACES (PYTHON SIGNATURES)
================================================================================

  Exact signatures to code against. Copy these into stubs first, then
  implement. The tests for each component can be written against the
  signatures before the implementation lands.


  # ------ config -----------------------------------------------------
  class Settings(BaseSettings): ...

  class AlgoParams(BaseModel):
      version: str
      clahe: CLAHEParams
      blur: BlurParams
      canny: CannyParams
      hough: HoughParams
      center_region: CenterRegionParams
      ransac: RansacParams
      confidence: ConfidenceParams
      tolerance: ToleranceParams

  def load_algo_params(version: str) -> AlgoParams

  class Calibration(BaseModel):
      calibration_id: str
      camera_side: Literal["L", "R"]
      mm_per_px: float
      method: str
      valid_from: datetime
      operator: str
      reference_image: str

  def load_calibration(path: Path) -> Calibration


  # ------ data -------------------------------------------------------
  def parse_filename(name: str) -> ParsedName

  def validate_image(image_bytes: bytes) ->
      tuple[np.ndarray | None, ValidationResult]

  async def wait_for_stable(path: Path,
      checks: int = 3, interval_ms: int = 150) -> None


  # ------ measurement ------------------------------------------------
  def measure_innermost_diameter(
      inp: PipelineInput) -> PipelineOutput

  def evaluate_status(
      diameter_mm: float, confidence: float,
      params: AlgoParams) -> Literal["PASS", "FAIL", "REVIEW", "ERROR"]


  # ------ persistence ------------------------------------------------
  class SessionRepository:
      async def create(self, record: SessionRow) -> SessionRow
      async def mark_stopped(self, id: UUID, summary: dict) -> None
      async def get(self, id: UUID) -> SessionRow | None

  class MeasurementRepository:
      async def insert(self, row: MeasurementRow) -> MeasurementRow
      async def get(self, id: UUID) -> MeasurementRow | None
      async def list_by_session(self,
          sid: UUID, since: datetime | None = None)
          -> list[MeasurementRow]
      async def get_pair(self, sid: UUID, chassis_no: str)
          -> tuple[MeasurementRow | None, MeasurementRow | None]

  class ChassisRepository:
      async def upsert(self, row: ChassisRow) -> ChassisRow
      async def search(self, chassis_no: str) -> list[ChassisRow]

  class DebugImageStore:
      async def put(self, key: str, jpeg: bytes) -> str
      async def stream(self, key: str) -> AsyncIterator[bytes]


  # ------ sessions ---------------------------------------------------
  class SessionManager:
      async def start(self, req: StartRequest) -> StartResponse
      async def stop(self, sid: UUID) -> StopResponse
      def require_active(self, sid: UUID) -> SessionRuntime

  class Aggregator:
      async def accept(self, m: MeasurementRow) -> None
      async def flush(self) -> None

  class FolderWatcher:
      def start(self) -> None
      def stop(self) -> None


  # ------ api (FastAPI schemas) --------------------------------------
  class StartRequest(BaseModel):
      started_by: str
      notes: str | None = None

  class StartResponse(BaseModel):
      session_id: UUID
      status: Literal["ACTIVE"]
      left_dir: str
      right_dir: str
      algo_params_version: str
      left_calibration: str
      right_calibration: str
      started_at: datetime

  # ... (full schemas in src/tad/api/schemas.py)



================================================================================
  10. CONFIGURATION FILE FORMATS
================================================================================

  10.1  algo_params YAML (configs/algo_params/algo-1.2.0.yaml)
  -----------------------------------------------------------

     version: "algo-1.2.0"
     clahe:
       clip_limit: 2.0
       tile_grid_size: [8, 8]
     blur:
       kernel: 5
     canny:
       lower_ratio: 0.66
       upper_ratio: 1.33
     hough:
       dp: 1.2
       min_dist: 40
       param1: 100
       param2: 30
       min_radius_px: 40
       max_radius_px: 160
     center_region:
       inner_fraction: 0.7
     ransac:
       iterations: 200
       inlier_threshold_px: 1.0
       seed: 42
     confidence:
       conf_pass: 0.85
       conf_review: 0.60
     tolerance:
       min_mm: 47.000
       max_mm: 47.500
       asymmetry_threshold_mm: 0.15


  10.2  calibration YAML (configs/calibration/cal-2026-03-14-L.yaml)
  -----------------------------------------------------------------

     calibration_id: "cal-2026-03-14-L"
     camera_side: "L"
     mm_per_px: 0.082340
     method: "checkerboard"
     valid_from: "2026-03-14T09:00:00Z"
     operator: "qa-technician-12"
     reference_image: "configs/calibration/images/cal-2026-03-14-L.jpg"


  10.3  .env (local dev)
  ----------------------

     DB_DSN=postgresql+psycopg://tad:tad@localhost:5432/tad
     MINIO_ENDPOINT=localhost:9000
     MINIO_ACCESS_KEY=minioadmin
     MINIO_SECRET_KEY=minioadmin
     MINIO_BUCKET=tad-debug

     IMAGES_LEFT_DIR=/tmp/tad/images/left
     IMAGES_RIGHT_DIR=/tmp/tad/images/right

     ALGO_PARAMS_VERSION=algo-1.2.0
     DEFAULT_CALIBRATION_LEFT=configs/calibration/cal-2026-03-14-L.yaml
     DEFAULT_CALIBRATION_RIGHT=configs/calibration/cal-2026-03-14-R.yaml

     ASYMMETRY_THRESHOLD_MM=0.15
     QUEUE_MAX_SIZE=256
     LOG_LEVEL=INFO



================================================================================
  11. LOCAL DEVELOPMENT SETUP
================================================================================

  ONE-TIME
     - Install Python 3.11 and Docker.
     - Clone repo; copy .env.example to .env.
     - uv venv   (or python -m venv .venv)
     - source .venv/bin/activate
     - uv pip install -e ".[dev]"   (or pip install -e ".[dev]")
     - pre-commit install

  STACK UP
     make up              # docker compose: postgres + minio
     make migrate         # alembic upgrade head
     make seed            # optional seed data

  RUN THE SERVICE
     make serve           # uvicorn src.tad.main:app --reload

  DROP IMAGES TO TEST
     cp tests/fixtures/images/MALBB51BLPM123456_L.jpg \
        /tmp/tad/images/left/
     cp tests/fixtures/images/MALBB51BLPM123456_R.jpg \
        /tmp/tad/images/right/

  CURL A SESSION
     curl -X POST http://localhost:8000/v1/sessions/start \
         -H "content-type: application/json" \
         -d '{"started_by":"dev", "notes":"local"}'

     # In another terminal, subscribe to events:
     curl -N http://localhost:8000/v1/sessions/<ID>/events

  TESTS
     make test            # ruff + mypy + pytest
     make test-unit
     make test-integration
     make eval            # run the locked eval harness



================================================================================
  12. IMPLEMENTATION ROADMAP (BUILD ORDER)
================================================================================

  Build in this order. Each step is independently testable. Do not
  skip ahead — the value is that each step is small and green.


  STEP 1 — PROJECT SCAFFOLD
     Goal: a project that runs, has lint/test, and can be served.
     - pyproject.toml with pinned deps
     - Makefile
     - Dockerfile + docker-compose (Postgres + MinIO)
     - Minimal FastAPI app at src/tad/main.py with /health
     - CI: ci.yml runs ruff + mypy + pytest (empty)
     Exit: make test is green; curl /health returns 200.


  STEP 2 — CONFIG LOADERS
     Goal: Settings, AlgoParams, Calibration load and validate.
     - Pydantic Settings reading .env
     - AlgoParams + load_algo_params(version)
     - Calibration + load_calibration(path)
     Exit: unit tests for all three; /ready returns 200.


  STEP 3 — FILENAME PARSER + IMAGE VALIDATOR
     Goal: pure functions, fully tested.
     - FILENAME_RE + parse_filename
     - validate_image with all gates
     Exit: 100% branch coverage on these modules.


  STEP 4 — MEASUREMENT PIPELINE (OFFLINE)
     Goal: a function that takes an image and returns a diameter.
     - preprocessing, edges, circle_detect, ransac_refine, confidence,
       annotate, pipeline
     - Fixture images under tests/fixtures/images/
     - Unit + property tests
     - CLI script: python -m tad.measurement.pipeline <image> <cal>
     Exit: on fixture images, measured diameter matches expected
     within 0.05 mm.


  STEP 5 — PERSISTENCE LAYER
     Goal: rows in Postgres, blobs in MinIO.
     - SQLAlchemy async engine; Alembic migration 001 with all tables
     - Repository classes with tests (against real Postgres in CI)
     - DebugImageStore with MinIO
     Exit: integration test inserts and reads a Measurement round-trip.


  STEP 6 — AGGREGATOR
     Goal: given two Measurements, produce a ChassisRecord.
     - Aggregator.accept with in-memory pending map
     - Status matrix (see TRD 7.1)
     - asymmetry threshold
     - flush() for orphans
     Exit: unit tests cover every cell of the status matrix plus the
     asymmetry downgrade and the orphan path.


  STEP 7 — SSE BROKER
     Goal: per-session fan-out with slow-subscriber protection.
     - In-memory subscribe/unsubscribe/publish
     - FastAPI route /v1/sessions/{id}/events
     Exit: integration test: two concurrent subscribers both see the
     same event; a slow one is dropped rather than stalling.


  STEP 8 — FOLDER WATCHERS + CONSUMER
     Goal: dropping a file into /tmp/tad/images/left triggers a
     measurement.
     - FolderWatcher using watchdog
     - Safe-read size-stability loop
     - process_item: validate -> parse -> measure (to_thread) ->
       upload -> insert -> publish -> aggregate
     Exit: end-to-end integration test spins up a SessionManager,
     drops fixture files, and asserts both events arrive.


  STEP 9 — SESSION MANAGER + API ROUTES
     Goal: the full lifecycle behind HTTP.
     - POST /sessions/start -> returns ACTIVE session
     - POST /sessions/{id}/stop -> returns summary
     - GET /sessions/{id}/results (polling fallback)
     - GET /v1/measurements/{id}, GET /v1/debug/{id}
     Exit: curl walkthrough in Section 11 works end to end.


  STEP 10 — OBSERVABILITY
     Goal: production-readiness hygiene.
     - structlog + request IDs
     - Prometheus /metrics with images_processed_total, latency
       histogram, chassis_results_total, confidence_score, etc.
     - Readiness probe verifies DB, MinIO, calibration, folders
     Exit: Prometheus scrapes the metric endpoint locally.


  STEP 11 — EVAL HARNESS
     Goal: locked test set + pass/fail gate.
     - tests/eval/dataset.csv (chassis_no, image_path, side,
       caliper_mm)
     - evals/eval.py reports MAE, P95, max error, per-side slice
     - eval.yml GH action runs on every PR and fails on regression
     Exit: the current pipeline passes the gate; a deliberate
     regression fails it.


  STEP 12 — HARDEN AND RELEASE
     Goal: ready for staging.
     - Error envelope standardisation
     - Retries and circuit breaker around DB writes
     - Graceful shutdown (in-flight items complete)
     - Dockerfile finalised (non-root user, healthcheck)
     - Release tag; cd.yml builds and pushes image
     Exit: staging runs a replay of real images through the service.



================================================================================
  13. TESTING STRATEGY (PER COMPONENT)
================================================================================

  Component            Test Kind              Notes
  -------------------  ---------------------  --------------------------
  Filename parser      Unit                   Valid + invalid cases,
                                              every rejection reason.
  Image validator      Unit                   Pre-built tiny images
                                              (too small, too blurry,
                                              overexposed, truncated).
  Pipeline             Unit + property        Synthetic circles with
                                              known radius; translation
                                              and rotation invariants.
  Calibration loader   Unit                   Missing file, bad YAML,
                                              side mismatch.
  Repositories         Integration (real PG)  Use pytest-docker or a
                                              pre-provisioned container.
  Blob store           Integration (MinIO)    Round-trip jpeg bytes.
  Aggregator           Unit                   Full status matrix +
                                              asymmetry + orphans.
  Broker               Unit (asyncio)         Fan-out, slow subscriber,
                                              unsubscribe on close.
  Folder watcher       Integration            Drop files, assert queue
                                              receives them in order.
  Session manager      Integration            Full start -> drop files
                                              -> stop cycle.
  API routes           Integration (httpx)    Each route's happy path
                                              and two error paths.
  Eval harness         System                 Runs nightly + every PR.


  CONVENTIONS
     - pytest-asyncio 'auto' mode; use async def tests throughout.
     - Fixtures live under tests/fixtures/ and are committed to the repo.
     - Time is never real in tests: use freezegun or pass a clock
       callable into classes that need "now".
     - Tests must not reach the network (except integration tests that
       target local Postgres/MinIO via docker-compose).



================================================================================
  14. DEPLOYMENT ARCHITECTURE
================================================================================

  PLANT-SIDE TOPOLOGY
  -------------------

     +----------------------------------------------------------+
     |                  Plant Server                            |
     |                                                          |
     |  +----------------+   +-------------+   +-------------+  |
     |  | tad-service    |-->| postgres    |   | minio       |  |
     |  | (this app)     |   |             |   |             |  |
     |  +--------+-------+   +-------------+   +------+------+  |
     |           |                                    ^         |
     |           | reads                              |         |
     |           v                                    | writes  |
     |  +---------------------+                       |         |
     |  | /images/left (nfs?) |                       |         |
     |  | /images/right (nfs?)|                       |         |
     |  +---------------------+                       |         |
     +----------------------------------------------------------+

  Everything is on the same Docker network. Postgres and MinIO have
  their own volumes. The image folders are mounted into the
  tad-service container as read-only.


  DOCKER COMPOSE (production-like)

     services:
       tad:
         image: registry.plant.internal/tad:${GIT_SHA}
         restart: unless-stopped
         env_file: /etc/tad/env
         volumes:
           - /plant/images/left:/images/left:ro
           - /plant/images/right:/images/right:ro
           - ./configs:/app/configs:ro
         ports:
           - "127.0.0.1:8000:8000"
         depends_on: [postgres, minio]
         healthcheck:
           test: ["CMD", "curl", "-f", "http://localhost:8000/v1/ready"]
           interval: 10s
           timeout: 2s
           retries: 3

       postgres:
         image: postgres:16
         volumes: [pgdata:/var/lib/postgresql/data]
         environment:
           POSTGRES_USER: tad
           POSTGRES_PASSWORD: ${PG_PASS}
           POSTGRES_DB: tad

       minio:
         image: minio/minio
         command: server /data --console-address ":9001"
         volumes: [miniodata:/data]
         environment:
           MINIO_ROOT_USER: ${MINIO_USER}
           MINIO_ROOT_PASSWORD: ${MINIO_PASS}


  ROLLOUT
     - Push image to the plant registry tagged with the git SHA.
     - On staging: docker compose pull && up -d.
     - Run replay_session.py against a recent day of images.
     - If outputs match the current production service within
       tolerance, tag the image for production and repeat on prod.



================================================================================
  15. OBSERVABILITY AND OPERATIONAL RUNBOOK
================================================================================

  LOGS
     - JSON format via structlog.
     - Every record includes session_id, chassis_no (hashed in info /
       warn; plaintext in debug), camera_side, measurement_id.
     - Error records include the exception class and correlation id.


  METRICS (Prometheus)
     Counter    images_processed_total{side, status}
     Counter    chassis_results_total{status}
     Counter    warnings_total{reason}
     Histogram  image_latency_seconds{side}
     Histogram  confidence_score{side}
     Histogram  diameter_mm{side}
     Histogram  asymmetry_mm
     Gauge      sessions_active
     Gauge      pending_chassis_count{session_id}


  ALERTS (starter set)
     - error rate (status=ERROR or HTTP 5xx) exceeds 2x 7-day baseline
     - manual review rate > 5 % over a 24 h window
     - ERR_NO_CIRCLE rate > 1 % over a 24 h window
     - asymmetry_mm p95 creeps above historical baseline
     - /ready has returned non-200 for more than 60 s


  RUNBOOK — QUICK ACTIONS
     Dashboard "loading" forever
        -> check /v1/ready; if 503, check Postgres + MinIO + folders
        -> re-check the two calibration YAML files exist and parse

     Many ERR_NO_CIRCLE events suddenly
        -> likely lighting change or capture cadence change
        -> inspect debug images; escalate to Plant Engineering

     Rising asymmetry without throughput change
        -> probable single-camera calibration drift
        -> run scripts/run_calibration.py for the suspect side

     Slow dashboard updates
        -> check sessions_active gauge and subscriber count
        -> if broker queue sizes are high, a slow client is blocking
           itself — the broker will drop it automatically



================================================================================
  16. CROSS-CUTTING CONCERNS
================================================================================

  IDEMPOTENCY
     - An image can be seen by the watcher more than once (fs flakiness).
     - process_item key is (session_id, absolute_path, file_mtime).
       Already-seen keys are no-ops with a debug log.

  DETERMINISM
     - numpy.random.Generator(seed=ransac.seed) created per call.
     - No time-based branches anywhere in measurement/*.
     - DB rows store algo_params_version and calibration_version so
       that any past measurement can be reproduced from source.

  ERROR ENVELOPE
     Every API error returns:

        {
          "error_code": "ERR_...",
          "error_message": "human-readable, actionable",
          "request_id": "rid-..."
        }

     5xx errors include a request_id that matches the log.

  GRACEFUL SHUTDOWN
     - SIGTERM triggers stop of all active sessions (same path as
       POST /stop for each), with a 30 s drain budget.
     - Uvicorn's lifespan event handlers orchestrate this.

  SECRETS
     - Loaded only from environment. Never logged. Never echoed.

  TIME
     - All timestamps are TIMESTAMPTZ in UTC in the database.
     - All log timestamps are UTC. The UI is responsible for rendering
       in the plant's local zone.



================================================================================
  17. APPENDIX — CODE SKETCHES FOR TRICKY BITS
================================================================================


  17.1  ADAPTIVE THRESHOLD + MORPH CLOSE (measurement/threshold.py)
  -----------------------------------------------------------------

     def adaptive_threshold(blurred_gray: np.ndarray,
                            *, block_size: int = 51,
                            c: int = 10) -> np.ndarray:
         return cv2.adaptiveThreshold(
             blurred_gray, 255,
             cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
             cv2.THRESH_BINARY_INV,
             block_size, c,
         )

     def morph_close(binary: np.ndarray,
                     *, kernel_size: int = 3,
                     iterations: int = 1) -> np.ndarray:
         kernel = np.ones((kernel_size, kernel_size), np.uint8)
         return cv2.morphologyEx(binary, cv2.MORPH_CLOSE,
                                 kernel, iterations=iterations)


  17.2  CONTOUR + MASKED HOUGH (measurement/contour_detect.py)
  ------------------------------------------------------------

     def find_candidate_contours(binary_mask,
                                  *, min_area: float = 50.0):
         contours, _ = cv2.findContours(
             binary_mask,
             cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
         )
         filtered = [c for c in contours
                     if cv2.contourArea(c) >= min_area]
         return sorted(filtered, key=cv2.contourArea, reverse=True)

     def detect_circle_in_contour(gray, contour, *,
                                   mm_per_px, target_diameter_mm,
                                   radius_tolerance_mm=0.3,
                                   dp=1.2, min_dist=10,
                                   param1=50, param2=20):
         ppm = 1.0 / mm_per_px
         min_r = int((target_diameter_mm - radius_tolerance_mm)
                     / 2.0 * ppm)
         max_r = int((target_diameter_mm + radius_tolerance_mm)
                     / 2.0 * ppm)

         mask = np.zeros_like(gray)
         cv2.drawContours(mask, [contour], -1, 255,
                          thickness=cv2.FILLED)
         masked_gray = cv2.bitwise_and(gray, gray, mask=mask)

         circles = cv2.HoughCircles(
             masked_gray, cv2.HOUGH_GRADIENT,
             dp=dp, minDist=min_dist,
             param1=param1, param2=param2,
             minRadius=min_r, maxRadius=max_r,
         )
         if circles is None:
             return None

         x, y, r = (float(v) for v in circles[0][0])
         return InnerCircle(cx=int(round(x)),
                            cy=int(round(y)),
                            radius_px=r, peak=1.0)

     def detect_circle(gray, binary_mask, ...):
         for c in find_candidate_contours(binary_mask, ...):
             circle = detect_circle_in_contour(gray, c, ...)
             if circle is not None:
                 return circle
         return None


  17.3  BAND-BASED CLASSIFICATION (measurement/confidence.py)
  -----------------------------------------------------------

     def evaluate_status(diameter_mm, target_mm, *,
                         ok_band_mm=0.2,
                         somewhat_ok_band_mm=0.5,
                         tolerance_min_mm=47.0,
                         tolerance_max_mm=47.5):
         if diameter_mm < tolerance_min_mm \
            or diameter_mm > tolerance_max_mm:
             return "FAIL"
         delta = abs(diameter_mm - target_mm)
         if delta <= ok_band_mm:       return "PASS"
         if delta <= somewhat_ok_band_mm: return "REVIEW"
         return "FAIL"


  17.4  FOLDER WATCHER -> ASYNC QUEUE (sessions/watcher.py)
  ---------------------------------------------------------

     class _Handler(FileSystemEventHandler):
         def __init__(self, loop, queue, side):
             self.loop = loop
             self.queue = queue
             self.side = side

         def on_created(self, event):
             if event.is_directory:
                 return
             path = Path(event.src_path)
             self.loop.call_soon_threadsafe(
                 self.queue.put_nowait,
                 QueueItem(side=self.side, path=path))

     class FolderWatcher:
         def __init__(self, side, path, queue):
             self._obs = Observer()
             self._obs.schedule(
                 _Handler(asyncio.get_running_loop(), queue, side),
                 str(path),
                 recursive=False)

         def start(self): self._obs.start()
         def stop(self):
             self._obs.stop()
             self._obs.join(timeout=5)


  17.5  PROCESS_ITEM LOOP (sessions/consumer.py)
  ----------------------------------------------

     async def process_item(item: QueueItem, ctx: SessionRuntime) -> None:
         try:
             await wait_for_stable(item.path)
             parsed = parse_filename(item.path.name)
             data = item.path.read_bytes()
             image, vr = validate_image(data)
             if not vr.ok:
                 await _emit_warning(ctx, parsed, item, vr)
                 return
             cal = ctx.calibrations[parsed.camera_side]
             t0 = time.perf_counter()
             output = await asyncio.to_thread(
                 measure_innermost_diameter,
                 PipelineInput(image, cal, ctx.algo_params))
             latency_ms = int((time.perf_counter() - t0) * 1000)

             debug_key = f"sessions/{ctx.session.session_id}/measurements/{uuid4()}.jpg"
             await ctx.blob_store.put(
                 debug_key, _to_jpeg(output.annotated_image))

             row = _measurement_row(ctx, parsed, item, output,
                                    cal, debug_key, latency_ms)
             await ctx.meas_repo.insert(row)

             await ctx.broker.publish(
                 Event(type="camera_result", payload=row.to_dto()))
             await ctx.aggregator.accept(row)

         except BadFilename as e:
             await _emit_warning(ctx, None, item,
                 ValidationResult.bad_filename(str(e)))
         except Exception as e:
             log.exception("process_item failed", path=str(item.path))
             await _emit_warning(ctx, None, item,
                 ValidationResult.internal(str(e)))


  17.6  STATUS MATRIX (sessions/aggregator.py)
  --------------------------------------------

     STATUS_MATRIX = {
         ("PASS",   "PASS"):   "PASS",
         ("PASS",   "REVIEW"): "REVIEW",
         ("PASS",   "FAIL"):   "FAIL",
         ("PASS",   "ERROR"):  "ERROR",
         ("REVIEW", "PASS"):   "REVIEW",
         ("REVIEW", "REVIEW"): "REVIEW",
         ("REVIEW", "FAIL"):   "FAIL",
         ("REVIEW", "ERROR"):  "ERROR",
         ("FAIL",   "PASS"):   "FAIL",
         ("FAIL",   "REVIEW"): "FAIL",
         ("FAIL",   "FAIL"):   "FAIL",
         ("FAIL",   "ERROR"):  "FAIL",
         ("ERROR",  "PASS"):   "ERROR",
         ("ERROR",  "REVIEW"): "ERROR",
         ("ERROR",  "FAIL"):   "FAIL",
         ("ERROR",  "ERROR"):  "ERROR",
     }

     def combine(left_status, right_status, asymmetry_mm, threshold):
         overall = STATUS_MATRIX[(left_status, right_status)]
         if overall == "PASS" and asymmetry_mm is not None \
            and asymmetry_mm > threshold:
             overall = "REVIEW"
         return overall


================================================================================
                      END OF DOCUMENT — ARCHITECTURE v1.0
================================================================================

### Diagrams (from architecture_diagram.md)

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
