"""
Complexity analysis result storage.

This module provides SQLite-based storage for complexity analysis results,
enabling historical trend tracking and performance regression detection.
"""

import os
import platform
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from ast_grep_mcp.constants import ComplexityStorageDefaults, PerformanceDefaults
from ast_grep_mcp.models.complexity import FunctionComplexity

# =============================================================================
# DATABASE SCHEMA
# =============================================================================

COMPLEXITY_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_path TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analysis_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    commit_hash TEXT,
    branch_name TEXT,
    run_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_functions INTEGER NOT NULL DEFAULT 0,
    total_files INTEGER NOT NULL DEFAULT 0,
    avg_cyclomatic REAL,
    avg_cognitive REAL,
    max_cyclomatic INTEGER,
    max_cognitive INTEGER,
    max_nesting INTEGER,
    threshold_violations INTEGER DEFAULT 0,
    analysis_duration_ms INTEGER,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS function_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    function_name TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    cyclomatic_complexity INTEGER NOT NULL,
    cognitive_complexity INTEGER NOT NULL,
    nesting_depth INTEGER NOT NULL,
    line_count INTEGER NOT NULL,
    parameter_count INTEGER,
    exceeds_threshold TEXT,
    FOREIGN KEY (run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_runs_project_timestamp ON analysis_runs(project_id, run_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_runs_commit ON analysis_runs(commit_hash);
CREATE INDEX IF NOT EXISTS idx_function_metrics_run ON function_metrics(run_id);
CREATE INDEX IF NOT EXISTS idx_function_metrics_complexity ON function_metrics(cyclomatic_complexity DESC);
"""


# =============================================================================
# MODULE-LEVEL HELPERS
# =============================================================================


def _build_run_params(
    project_id: int,
    commit_hash: Optional[str],
    branch_name: Optional[str],
    results: Dict[str, Any],
) -> tuple[Any, ...]:
    return (
        project_id,
        commit_hash,
        branch_name,
        results.get("total_functions", 0),
        results.get("total_files", 0),
        results.get("avg_cyclomatic"),
        results.get("avg_cognitive"),
        results.get("max_cyclomatic"),
        results.get("max_cognitive"),
        results.get("max_nesting"),
        results.get("violation_count", 0),
        results.get("duration_ms"),
    )


def _build_function_rows(functions: List[FunctionComplexity]) -> List[tuple[Any, ...]]:
    return [
        (
            f.file_path,
            f.function_name,
            f.start_line,
            f.end_line,
            f.metrics.cyclomatic,
            f.metrics.cognitive,
            f.metrics.nesting_depth,
            f.metrics.lines,
            f.metrics.parameter_count,
            ",".join(f.exceeds) if f.exceeds else None,
        )
        for f in functions
    ]


_INSERT_RUN_SQL = """
    INSERT INTO analysis_runs (
        project_id, commit_hash, branch_name,
        total_functions, total_files,
        avg_cyclomatic, avg_cognitive,
        max_cyclomatic, max_cognitive, max_nesting,
        threshold_violations, analysis_duration_ms
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_INSERT_METRICS_SQL = """
    INSERT INTO function_metrics (
        run_id, file_path, function_name,
        start_line, end_line,
        cyclomatic_complexity, cognitive_complexity,
        nesting_depth, line_count, parameter_count,
        exceeds_threshold
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_SELECT_TRENDS_SQL = """
    SELECT
        ar.run_timestamp,
        ar.commit_hash,
        ar.branch_name,
        ar.total_functions,
        ar.avg_cyclomatic,
        ar.avg_cognitive,
        ar.max_cyclomatic,
        ar.max_cognitive,
        ar.threshold_violations
    FROM analysis_runs ar
    JOIN projects p ON ar.project_id = p.id
    WHERE p.project_path = ?
        AND ar.run_timestamp >= datetime('now', ?)
    ORDER BY ar.run_timestamp ASC
"""


def _insert_run(conn: sqlite3.Connection, run_params: tuple[Any, ...]) -> int:
    cursor = conn.execute(_INSERT_RUN_SQL, run_params)
    return cursor.lastrowid or 0


def _insert_function_metrics(conn: sqlite3.Connection, run_id: int, function_rows: List[tuple[Any, ...]]) -> None:
    if function_rows:
        rows_with_id = [(run_id,) + row for row in function_rows]
        conn.executemany(_INSERT_METRICS_SQL, rows_with_id)


# =============================================================================
# STORAGE CLASS
# =============================================================================


class ComplexityStorage:
    """SQLite storage for complexity analysis results."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or self._get_default_db_path()
        self._init_db()

    def _get_default_db_path(self) -> Path:
        """Get default database path in user's data directory."""
        if platform.system() == "Darwin":
            base = Path.home() / "Library" / "Application Support" / "ast-grep-mcp"
        elif platform.system() == "Windows":
            base = Path(os.environ.get("APPDATA", str(Path.home()))) / "ast-grep-mcp"
        else:
            base = Path.home() / ".local" / "share" / "ast-grep-mcp"

        base.mkdir(parents=True, exist_ok=True)
        return base / "complexity.db"

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path), timeout=PerformanceDefaults.DATABASE_TIMEOUT_SECONDS)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        ok = False
        try:
            yield conn
            ok = True
        finally:
            if ok:
                conn.commit()
            else:
                conn.rollback()
            conn.close()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript(COMPLEXITY_DB_SCHEMA)

    def get_or_create_project(self, project_path: str) -> int:
        """Get or create project entry, return project ID."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT id FROM projects WHERE project_path = ?", (project_path,))
            row = cursor.fetchone()
            if row:
                return int(row["id"])

            cursor = conn.execute("INSERT INTO projects (project_path, name) VALUES (?, ?)", (project_path, Path(project_path).name))
            return cursor.lastrowid or 0

    def store_analysis_run(
        self,
        project_path: str,
        results: Dict[str, Any],
        functions: List[FunctionComplexity],
        commit_hash: Optional[str] = None,
        branch_name: Optional[str] = None,
    ) -> int:
        """Store complete analysis run with all metrics."""
        project_id = self.get_or_create_project(project_path)
        run_params = _build_run_params(project_id, commit_hash, branch_name, results)
        function_rows = _build_function_rows(functions)

        with self._get_connection() as conn:
            run_id = _insert_run(conn, run_params)
            _insert_function_metrics(conn, run_id, function_rows)
            return run_id

    def get_project_trends(self, project_path: str, days: int = ComplexityStorageDefaults.TRENDS_LOOKBACK_DAYS) -> List[Dict[str, Any]]:
        """Get complexity trends for a project over time."""
        with self._get_connection() as conn:
            cursor = conn.execute(_SELECT_TRENDS_SQL, (project_path, f"-{days} days"))
            rows = cursor.fetchall()
        return [dict(row) for row in rows]
