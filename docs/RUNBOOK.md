# Runbook — Trailing-Arm Detection (TAD)

## 1. Local development
    make setup          # install deps
    make test           # run unit + integration tests
    make lint
    make demo           # in-memory backend on :8000
    make demo-seed      # synthetic image burst

## 2. Single-port Docker
    docker compose up --build
The container serves backend + frontend on the same port (per ADR-009 /
TRD).

## 3. Production deployment
1. Provision host with Docker.
2. Configure `.env` from `.env.example` (calibration paths, image
   watch folders, DB URL, blob store creds).
3. Place calibration YAMLs in `configs/calibration/`:
     cal-<YYYY-MM-DD>-L.yaml
     cal-<YYYY-MM-DD>-R.yaml
4. `docker compose -f docker-compose.yml up -d`.
5. Verify health: `curl http://<host>:<port>/health`.

## 4. Common operations
- **New algorithm version**: add `configs/algo_params/algo-<X.Y.Z>.yaml`,
  bump pinned version, run `make eval`, open ADR if regression.
- **New calibration**: drop YAMLs into `configs/calibration/`, restart
  service. Calibrations are immutable per session.
- **DB migration**: `alembic upgrade head`.
- **Inspect a session**: dashboard → session detail → annotated images.

## 5. Troubleshooting
| Symptom | Likely cause | Action |
| ------- | ------------ | ------ |
| Image rejected | Filename format | Verify `<CHASSIS>_{L,R}.jpg`, no I/O/Q |
| Asymmetry too high | Stale calibration | Re-run calibration; reload service |
| Eval MAE regression | Threshold drift | Re-baseline, open ADR |
| SSE disconnects | Reverse proxy buffer | Disable proxy buffering for /sse |

## 6. Backup & restore
- Postgres: nightly pg_dump.
- MinIO blob store: weekly snapshot.

## 7. On-call
- Primary: <fill in>
- Escalation: <fill in>
