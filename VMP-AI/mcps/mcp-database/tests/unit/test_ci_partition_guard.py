"""The integration suite is partitioned by marker with no gaps.

The `tests` job runs `-m "not cross_engine and not cluster"` (the per-engine files) then
`-m cross_engine`; the `compat` matrix runs `test_<engine>_integration.py`; the `cluster` job runs
`-m cluster`. All three live in `test.yml`. A new integration file must land in exactly one of those
destinations — this guard makes the partition explicit and turns a missing marker into a fast
unit-test failure.
"""

import pathlib

# Files the compat matrix runs by name — keep in sync with the matrix in .github/workflows/test.yml.
MATRIX_PER_ENGINE = {
    "test_postgres_integration.py",
    "test_mysql_integration.py",
    "test_mariadb_integration.py",
    "test_sqlite_integration.py",
    "test_redis_integration.py",
    "test_mongodb_integration.py",
    "test_search_integration.py",
}

INTEGRATION_DIR = pathlib.Path(__file__).resolve().parent.parent / "integration"


def test_every_integration_file_runs_somewhere():
    """Each integration test file is either a per-engine matrix file or marked cross_engine."""
    orphans = [
        path.name
        for path in sorted(INTEGRATION_DIR.glob("test_*.py"))
        if path.name not in MATRIX_PER_ENGINE
        and "mark.cross_engine" not in (text := path.read_text(encoding="utf-8"))
        and "mark.cluster" not in text
    ]
    assert not orphans, (
        f"these integration files run in neither the CI matrix, the cross job nor the cluster job: {orphans}. "
        "Mark them with pytest.mark.cross_engine or pytest.mark.cluster, "
        "or add a matrix entry and list them in MATRIX_PER_ENGINE."
    )
