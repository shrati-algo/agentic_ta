"""Benchmark suite — wraps the locked eval harness in pytest."""
import csv
from pathlib import Path

DATASET = Path(__file__).parent / "dataset.csv"


def test_dataset_parses():
    assert DATASET.exists(), "tests/benchmark/dataset.csv missing"
    with DATASET.open() as f:
        rows = list(csv.DictReader(f))
    assert isinstance(rows, list)


# When ready, expand to call src.tad.evals.eval and assert MAE <= threshold.
# Keep this file deterministic — fail loudly on regression rather than
# tolerating drift.
