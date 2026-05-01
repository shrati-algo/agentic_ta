# Business Requirements Document — Trailing-Arm Detection (TAD)

**Status:** Draft v1.0
**Owner:** <fill in>
**Last updated:** 2026-05-01

## 1. Problem Statement
Assembly-line operators measure the innermost circle diameter on
trailing-arm suspension components manually using calipers. This is slow,
inconsistent, and error-prone, leading to QA escapes and rework.

## 2. Business Goals
- Replace manual caliper measurement with an automated CV system that
  reads a dual-camera (left + right) chassis pair and outputs a diameter
  in millimeters.
- Stream live measurements + asymmetry status to a dashboard for
  shift-level visibility.
- Maintain audit-grade traceability: every measurement pins algorithm
  version + calibration version.

## 3. Success Metrics
- MAE vs caliper ≤ <fill> mm on the locked eval set.
- P95 error ≤ <fill> mm.
- 100% of measurements carry algo + calibration version.
- Dashboard live latency < 2 s (image-drop → display).

## 4. Stakeholders
- Line operators: drop image pairs, see PASS/REVIEW/FAIL outcome.
- QA managers: dashboard, exception triage, decision audit trail.
- Process engineers: parameter tuning + calibration workflow.

## 5. Scope
In scope: dual-camera chassis pair (L/R), classical CV measurement,
single-port FastAPI + React deployment.
Out of scope: ML-based measurement (see ADR-001), multi-camera-per-side
fusion (deferred), 3D reconstruction.

## 6. Constraints & Assumptions
- Classical CV only — no ML model (ADR-001).
- Algorithm pinned per measurement (ADR-008 — Hough + contour).
- Calibration locked at session start.
- Single uvicorn worker (per CLAUDE.md).

## 7. Acceptance
- BRD signed off by QA manager.
- PRD/TRD aligned (cross-reference).
- `make eval` MAE within target on locked eval set.
- `make bench` green at v1.0.
