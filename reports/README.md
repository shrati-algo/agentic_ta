# reports/

Per-run outputs from `make bench` and (later) audit agents.

- `benchmark/`: accuracy reports per run, using `TEMPLATE.md` shape.
- `audits/`: reserved for future code/data/MLOps audit agents.

Reports are append-only. Do not overwrite past reports — diff against
them to spot regressions.
