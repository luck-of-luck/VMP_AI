"""
API/Tool Usage Tracking and Cost Monitoring.

This module provides comprehensive tracking for MCP tool executions including:
- Execution counts and timing
- Operation cost estimation
- Success/failure rates
- Performance metrics
- Usage alerts and thresholds

Storage: SQLite database for lightweight, file-based persistence.
"""

import hashlib
import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional, TypeVar, cast

from pydantic import BaseModel, Field

from ast_grep_mcp.constants import ConversionFactors, DisplayDefaults, FormattingDefaults, UsageTrackingDefaults

from .logging import get_logger

logger = get_logger("usage_tracking")


# =============================================================================
# Pricing Configuration
# =============================================================================


class OperationType(str, Enum):
    """Types of operations tracked for cost estimation."""

    # Search operations
    SEARCH_CODE = "search_code"
    FIND_DUPLICATION = "find_duplication"
    SIMILARITY_CALCULATION = "similarity_calculation"

    # Analysis operations
    ANALYZE_COMPLEXITY = "analyze_complexity"
    DETECT_CODE_SMELLS = "detect_code_smells"
    SECURITY_SCAN = "security_scan"

    # Refactoring operations
    RENAME_SYMBOL = "rename_symbol"
    EXTRACT_FUNCTION = "extract_function"
    APPLY_REWRITE = "apply_rewrite"

    # Documentation operations
    GENERATE_DOCS = "generate_docs"
    SYNC_CHECK = "sync_check"

    # Schema operations
    VALIDATE_SCHEMA = "validate_schema"
    ENHANCE_SCHEMA = "enhance_schema"

    # Generic
    UNKNOWN = "unknown"


@dataclass
class OperationPricing:
    """Cost estimation for an operation type.

    Costs are in "compute units" - abstract units representing
    computational effort. Can be mapped to actual costs if needed.
    """

    base_cost: float  # Base cost per operation
    per_file_cost: float = 0.0  # Additional cost per file processed
    per_line_cost: float = 0.0  # Additional cost per line analyzed
    per_match_cost: float = 0.0  # Additional cost per match found


# Operation pricing table (compute units)
# Calibrated based on typical execution times and resource usage
OPERATION_PRICING: Dict[OperationType, OperationPricing] = {
    # Search operations (relatively cheap)
    OperationType.SEARCH_CODE: OperationPricing(
        base_cost=0.001,
        per_file_cost=0.0001,
        per_match_cost=0.00001,
    ),
    OperationType.FIND_DUPLICATION: OperationPricing(
        base_cost=0.01,
        per_file_cost=0.001,
        per_line_cost=0.00001,
    ),
    OperationType.SIMILARITY_CALCULATION: OperationPricing(
        base_cost=0.001,
        per_line_cost=0.00001,
    ),
    # Analysis operations (moderate cost)
    OperationType.ANALYZE_COMPLEXITY: OperationPricing(
        base_cost=0.005,
        per_file_cost=0.001,
        per_line_cost=0.00001,
    ),
    OperationType.DETECT_CODE_SMELLS: OperationPricing(
        base_cost=0.01,
        per_file_cost=0.002,
    ),
    OperationType.SECURITY_SCAN: OperationPricing(
        base_cost=0.02,
        per_file_cost=0.003,
    ),
    # Refactoring operations (higher cost - modifies files)
    OperationType.RENAME_SYMBOL: OperationPricing(
        base_cost=0.05,
        per_file_cost=0.01,
    ),
    OperationType.EXTRACT_FUNCTION: OperationPricing(
        base_cost=0.1,
        per_file_cost=0.02,
    ),
    OperationType.APPLY_REWRITE: OperationPricing(
        base_cost=0.02,
        per_file_cost=0.005,
    ),
    # Documentation operations
    OperationType.GENERATE_DOCS: OperationPricing(
        base_cost=0.01,
        per_file_cost=0.002,
    ),
    OperationType.SYNC_CHECK: OperationPricing(
        base_cost=0.005,
        per_file_cost=0.001,
    ),
    # Schema operations
    OperationType.VALIDATE_SCHEMA: OperationPricing(
        base_cost=0.005,
    ),
    OperationType.ENHANCE_SCHEMA: OperationPricing(
        base_cost=0.01,
    ),
    # Unknown/generic
    OperationType.UNKNOWN: OperationPricing(
        base_cost=0.01,
    ),
}


def calculate_operation_cost(
    operation: OperationType,
    files_processed: int = 0,
    lines_analyzed: int = 0,
    matches_found: int = 0,
) -> float:
    """Calculate the estimated cost for an operation.

    Args:
        operation: Type of operation performed
        files_processed: Number of files processed
        lines_analyzed: Number of lines analyzed
        matches_found: Number of matches/results found

    Returns:
        Estimated cost in compute units
    """
    pricing = OPERATION_PRICING.get(operation, OPERATION_PRICING[OperationType.UNKNOWN])

    cost = pricing.base_cost
    cost += pricing.per_file_cost * files_processed
    cost += pricing.per_line_cost * lines_analyzed
    cost += pricing.per_match_cost * matches_found

    return cost


# =============================================================================
# Pydantic Models
# =============================================================================


class UsageLogEntry(BaseModel):
    """A single usage log entry."""

    id: str = Field(
        default_factory=lambda: hashlib.sha256(f"{time.time()}-{os.getpid()}".encode()).hexdigest()[
            : UsageTrackingDefaults.USAGE_ID_HASH_LENGTH
        ]
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tool_name: str
    operation_type: OperationType = OperationType.UNKNOWN
    success: bool = True
    error_message: Optional[str] = None
    response_time_ms: int = 0
    estimated_cost: float = 0.0
    files_processed: int = 0
    lines_analyzed: int = 0
    matches_found: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UsageStats(BaseModel):
    """Aggregated usage statistics."""

    period_start: datetime
    period_end: datetime
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    success_rate: float = 0.0
    total_cost: float = 0.0
    average_cost: float = 0.0
    total_response_time_ms: int = 0
    average_response_time_ms: float = 0.0
    calls_by_tool: Dict[str, int] = Field(default_factory=dict)
    calls_by_operation: Dict[str, int] = Field(default_factory=dict)
    cost_by_tool: Dict[str, float] = Field(default_factory=dict)


class UsageAlert(BaseModel):
    """A usage alert/warning."""

    level: str  # "info", "warning", "critical"
    message: str
    metric: str
    current_value: float
    threshold: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AlertThresholds(BaseModel):
    """Configurable alert thresholds."""

    # Daily thresholds
    daily_calls_warning: int = UsageTrackingDefaults.DAILY_CALLS_WARNING
    daily_calls_critical: int = UsageTrackingDefaults.DAILY_CALLS_CRITICAL
    daily_cost_warning: float = UsageTrackingDefaults.DAILY_COST_WARNING
    daily_cost_critical: float = UsageTrackingDefaults.DAILY_COST_CRITICAL

    # Error thresholds
    hourly_failures_warning: int = UsageTrackingDefaults.HOURLY_FAILURES_WARNING
    hourly_failures_critical: int = UsageTrackingDefaults.HOURLY_FAILURES_CRITICAL
    failure_rate_warning: float = UsageTrackingDefaults.FAILURE_RATE_WARNING
    failure_rate_critical: float = UsageTrackingDefaults.FAILURE_RATE_CRITICAL

    # Performance thresholds
    avg_response_time_warning_ms: int = UsageTrackingDefaults.AVG_RESPONSE_TIME_WARNING_MS
    avg_response_time_critical_ms: int = UsageTrackingDefaults.AVG_RESPONSE_TIME_CRITICAL_MS


# =============================================================================
# SQLite Storage
# =============================================================================


_INSERT_USAGE_SQL = """
    INSERT INTO usage_logs (
        id, timestamp, tool_name, operation_type, success,
        error_message, response_time_ms, estimated_cost,
        files_processed, lines_analyzed, matches_found, metadata
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def _entry_to_params(entry: UsageLogEntry) -> tuple[Any, ...]:
    return (
        entry.id,
        entry.timestamp.isoformat(),
        entry.tool_name,
        entry.operation_type.value,
        1 if entry.success else 0,
        entry.error_message,
        entry.response_time_ms,
        entry.estimated_cost,
        entry.files_processed,
        entry.lines_analyzed,
        entry.matches_found,
        json.dumps(entry.metadata) if entry.metadata else None,
    )


def _row_to_log_entry(row: sqlite3.Row) -> UsageLogEntry:
    return UsageLogEntry(
        id=row["id"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
        tool_name=row["tool_name"],
        operation_type=OperationType(row["operation_type"]),
        success=bool(row["success"]),
        error_message=row["error_message"],
        response_time_ms=row["response_time_ms"],
        estimated_cost=row["estimated_cost"],
        files_processed=row["files_processed"],
        lines_analyzed=row["lines_analyzed"],
        matches_found=row["matches_found"],
        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
    )


_STATS_AGGREGATE_SQL = """
    SELECT
        COUNT(*) as total_calls,
        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_calls,
        SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed_calls,
        SUM(estimated_cost) as total_cost,
        AVG(estimated_cost) as avg_cost,
        SUM(response_time_ms) as total_response_time,
        AVG(response_time_ms) as avg_response_time
    FROM usage_logs
    WHERE timestamp >= ? AND timestamp <= ?
"""


def _parse_stats_row(row: sqlite3.Row, start_time: datetime, end_time: datetime) -> dict[str, Any]:
    total_calls = row["total_calls"] or 0
    successful_calls = row["successful_calls"] or 0
    rate = (successful_calls / total_calls * ConversionFactors.PERCENT_MULTIPLIER) if total_calls > 0 else 0.0
    return {
        "period_start": start_time,
        "period_end": end_time,
        "total_calls": total_calls,
        "successful_calls": successful_calls,
        "failed_calls": row["failed_calls"] or 0,
        "success_rate": rate,
        "total_cost": row["total_cost"] or 0.0,
        "average_cost": row["avg_cost"] or 0.0,
        "total_response_time_ms": row["total_response_time"] or 0,
        "average_response_time_ms": row["avg_response_time"] or 0.0,
    }


def _db_calls_by_tool(conn: sqlite3.Connection, start_iso: str, end_iso: str) -> Dict[str, int]:
    rows = conn.execute(
        "SELECT tool_name, COUNT(*) as count FROM usage_logs WHERE timestamp >= ? AND timestamp <= ? GROUP BY tool_name",
        (start_iso, end_iso),
    )
    return {r["tool_name"]: r["count"] for r in rows}


def _db_calls_by_operation(conn: sqlite3.Connection, start_iso: str, end_iso: str) -> Dict[str, int]:
    rows = conn.execute(
        "SELECT operation_type, COUNT(*) as count FROM usage_logs WHERE timestamp >= ? AND timestamp <= ? GROUP BY operation_type",
        (start_iso, end_iso),
    )
    return {r["operation_type"]: r["count"] for r in rows}


def _db_cost_by_tool(conn: sqlite3.Connection, start_iso: str, end_iso: str) -> Dict[str, float]:
    rows = conn.execute(
        "SELECT tool_name, SUM(estimated_cost) as total_cost FROM usage_logs WHERE timestamp >= ? AND timestamp <= ? GROUP BY tool_name",
        (start_iso, end_iso),
    )
    return {r["tool_name"]: r["total_cost"] or 0.0 for r in rows}


def _make_alert(level: str, metric: str, value: float, threshold: float, fmt: str = "") -> UsageAlert:
    formatted = f"{value:{fmt}}" if fmt else str(int(value))
    return UsageAlert(
        level=level,
        message=f"{metric.replace('_', ' ').title()} ({formatted}) exceeded {level} threshold",
        metric=metric,
        current_value=value,
        threshold=threshold,
    )


def _threshold_alert(
    alerts: List[UsageAlert],
    metric: str,
    value: float,
    warning: float,
    critical: float,
    fmt: str = "",
) -> None:
    if value >= critical:
        alerts.append(_make_alert("critical", metric, value, critical, fmt))
    elif value >= warning:
        alerts.append(_make_alert("warning", metric, value, warning, fmt))


class UsageDatabase:
    """SQLite-based usage tracking database."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize the database.

        Args:
            db_path: Path to SQLite database. Defaults to ~/.ast-grep-mcp/usage.db
        """
        if db_path is None:
            config_dir = Path.home() / ".ast-grep-mcp"
            config_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(config_dir / "usage.db")

        self.db_path = db_path
        self._local = threading.local()
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "connection"):
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
            )
            self._local.connection.row_factory = sqlite3.Row
        return cast(sqlite3.Connection, self._local.connection)

    def _init_schema(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS usage_logs (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                operation_type TEXT NOT NULL,
                success INTEGER NOT NULL DEFAULT 1,
                error_message TEXT,
                response_time_ms INTEGER NOT NULL DEFAULT 0,
                estimated_cost REAL NOT NULL DEFAULT 0.0,
                files_processed INTEGER NOT NULL DEFAULT 0,
                lines_analyzed INTEGER NOT NULL DEFAULT 0,
                matches_found INTEGER NOT NULL DEFAULT 0,
                metadata TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON usage_logs(timestamp);
            CREATE INDEX IF NOT EXISTS idx_usage_tool ON usage_logs(tool_name);
            CREATE INDEX IF NOT EXISTS idx_usage_operation ON usage_logs(operation_type);
            CREATE INDEX IF NOT EXISTS idx_usage_success ON usage_logs(success);
        """)
        conn.commit()

    def log_usage(self, entry: UsageLogEntry) -> None:
        """Log a usage entry to the database.

        Args:
            entry: Usage log entry to persist
        """
        try:
            conn = self._get_connection()
            params = _entry_to_params(entry)
            conn.execute(_INSERT_USAGE_SQL, params)
            conn.commit()
            logger.debug(
                "usage_logged",
                tool=entry.tool_name,
                cost=f"{entry.estimated_cost:.6f}",
                response_time_ms=entry.response_time_ms,
            )
        except Exception as e:
            logger.error("usage_log_failed", error=str(e)[: DisplayDefaults.ERROR_OUTPUT_PREVIEW_LENGTH])

    def get_stats(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> UsageStats:
        """Get aggregated usage statistics.

        Args:
            start_time: Start of period (default: 7 days ago)
            end_time: End of period (default: now)

        Returns:
            Aggregated usage statistics
        """
        if start_time is None:
            start_time = datetime.now(UTC) - timedelta(days=UsageTrackingDefaults.DEFAULT_STATS_LOOKBACK_DAYS)
        if end_time is None:
            end_time = datetime.now(UTC)

        conn = self._get_connection()
        start_iso, end_iso = start_time.isoformat(), end_time.isoformat()

        row = conn.execute(_STATS_AGGREGATE_SQL, (start_iso, end_iso)).fetchone()
        fields = _parse_stats_row(row, start_time, end_time)
        return UsageStats(
            **fields,
            calls_by_tool=_db_calls_by_tool(conn, start_iso, end_iso),
            calls_by_operation=_db_calls_by_operation(conn, start_iso, end_iso),
            cost_by_tool=_db_cost_by_tool(conn, start_iso, end_iso),
        )

    def get_alerts(
        self,
        thresholds: Optional[AlertThresholds] = None,
    ) -> List[UsageAlert]:
        """Check for usage alerts based on thresholds.

        Args:
            thresholds: Alert thresholds (uses defaults if not provided)

        Returns:
            List of active alerts
        """
        if thresholds is None:
            thresholds = AlertThresholds()

        alerts: List[UsageAlert] = []
        now = datetime.now(UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        hour_ago = now - timedelta(hours=1)
        conn = self._get_connection()

        daily_calls = conn.execute(
            "SELECT COUNT(*) FROM usage_logs WHERE timestamp >= ?",
            (today_start.isoformat(),),
        ).fetchone()[0]
        _threshold_alert(alerts, "daily_calls", daily_calls, thresholds.daily_calls_warning, thresholds.daily_calls_critical)

        daily_cost = (
            conn.execute(
                "SELECT SUM(estimated_cost) FROM usage_logs WHERE timestamp >= ?",
                (today_start.isoformat(),),
            ).fetchone()[0]
            or 0.0
        )
        _threshold_alert(alerts, "daily_cost", daily_cost, thresholds.daily_cost_warning, thresholds.daily_cost_critical, ".4f")

        hourly_failures = conn.execute(
            "SELECT COUNT(*) FROM usage_logs WHERE timestamp >= ? AND success = 0",
            (hour_ago.isoformat(),),
        ).fetchone()[0]
        _threshold_alert(
            alerts,
            "hourly_failures",
            hourly_failures,
            thresholds.hourly_failures_warning,
            thresholds.hourly_failures_critical,
        )

        hourly_total = conn.execute(
            "SELECT COUNT(*) FROM usage_logs WHERE timestamp >= ?",
            (hour_ago.isoformat(),),
        ).fetchone()[0]
        if hourly_total > 0:
            failure_rate = hourly_failures / hourly_total
            _threshold_alert(alerts, "failure_rate", failure_rate, thresholds.failure_rate_warning, thresholds.failure_rate_critical, ".1%")

        return alerts

    def get_recent_logs(
        self,
        limit: int = UsageTrackingDefaults.DEFAULT_PAGINATION_LIMIT,
        tool_name: Optional[str] = None,
        success: Optional[bool] = None,
    ) -> List[UsageLogEntry]:
        """Get recent usage logs.

        Args:
            limit: Maximum number of logs to return
            tool_name: Filter by tool name
            success: Filter by success status

        Returns:
            List of recent usage log entries
        """
        conn = self._get_connection()

        query = "SELECT * FROM usage_logs WHERE 1=1"
        params: List[Any] = []

        if tool_name is not None:
            query += " AND tool_name = ?"
            params.append(tool_name)

        if success is not None:
            query += " AND success = ?"
            params.append(1 if success else 0)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        return [_row_to_log_entry(row) for row in conn.execute(query, params)]


# =============================================================================
# Global Tracker Instance
# =============================================================================


_usage_db: Optional[UsageDatabase] = None
_db_lock = threading.Lock()


def get_usage_database() -> UsageDatabase:
    """Get the global usage database instance."""
    global _usage_db
    if _usage_db is None:
        with _db_lock:
            if _usage_db is None:
                _usage_db = UsageDatabase()
    return _usage_db


# =============================================================================
# Tracking Decorator
# =============================================================================

F = TypeVar("F", bound=Callable[..., Any])


def _extract_result_metrics(result: Any) -> tuple[int, int, int]:
    """Extract (files_processed, lines_analyzed, matches_found) from a dict result."""
    if not isinstance(result, dict):
        return 0, 0, 0
    files = result.get("files_processed", 0)
    lines = result.get("lines_analyzed", 0)
    matches = result.get("matches_found", len(result.get("matches", [])))
    summary = result.get("summary", {})
    if summary:
        files = summary.get("total_files", files)
        matches = summary.get("total_matches", matches)
    return files, lines, matches


def _log_usage_entry(
    tool_name: str,
    operation_type: OperationType,
    success: bool,
    error_message: Optional[str],
    response_time_ms: int,
    files_processed: int,
    lines_analyzed: int,
    matches_found: int,
) -> None:
    estimated_cost = calculate_operation_cost(
        operation_type,
        files_processed=files_processed,
        lines_analyzed=lines_analyzed,
        matches_found=matches_found,
    )
    entry = UsageLogEntry(
        tool_name=tool_name,
        operation_type=operation_type,
        success=success,
        error_message=error_message,
        response_time_ms=response_time_ms,
        estimated_cost=estimated_cost,
        files_processed=files_processed,
        lines_analyzed=lines_analyzed,
        matches_found=matches_found,
    )
    try:
        get_usage_database().log_usage(entry)
    except Exception as log_error:
        logger.error("usage_tracking_failed", error=str(log_error)[: DisplayDefaults.ERROR_OUTPUT_PREVIEW_LENGTH])


class _TrackedWrapper:
    """Callable wrapper that tracks usage metrics for a function."""

    def __init__(self, func: Callable[..., Any], tool_name: str, operation_type: OperationType) -> None:
        self._func = func
        self._tool_name = tool_name
        self._operation_type = operation_type
        wraps(func)(self)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        start_time = time.perf_counter()
        success = True
        error_message: Optional[str] = None
        result: Any = None
        try:
            result = self._func(*args, **kwargs)
            return result
        except Exception as e:
            success = False
            error_message = str(e)[: DisplayDefaults.ERROR_MESSAGE_MAX_LENGTH]
            raise
        finally:
            ms = int((time.perf_counter() - start_time) * ConversionFactors.MILLISECONDS_PER_SECOND)
            files, lines, matches = _extract_result_metrics(result)
            _log_usage_entry(self._tool_name, self._operation_type, success, error_message, ms, files, lines, matches)


def _make_tracked_wrapper(func: F, tool_name: str, operation_type: OperationType) -> F:
    return cast(F, _TrackedWrapper(func, tool_name, operation_type))


def track_usage(
    tool_name: str,
    operation_type: OperationType = OperationType.UNKNOWN,
) -> Callable[[F], F]:
    """Decorator to track usage of a function/tool.

    Args:
        tool_name: Name of the tool being tracked
        operation_type: Type of operation for cost calculation

    Returns:
        Decorated function with usage tracking
    """

    def decorator(func: F) -> F:
        return _make_tracked_wrapper(func, tool_name, operation_type)

    return decorator


@contextmanager
def track_operation(
    tool_name: str,
    operation_type: OperationType = OperationType.UNKNOWN,
    metadata: Optional[Dict[str, Any]] = None,
) -> Generator["_OperationTracker", None, None]:
    """Context manager for tracking an operation.

    Usage:
        with track_operation("find_duplication", OperationType.FIND_DUPLICATION) as tracker:
            # perform operation
            tracker.files_processed = 10
            tracker.matches_found = 5

    Args:
        tool_name: Name of the tool
        operation_type: Type of operation
        metadata: Additional metadata to log
    """
    tracker = _OperationTracker(
        tool_name=tool_name,
        operation_type=operation_type,
        metadata=metadata or {},
    )
    tracker._start_time = time.perf_counter()

    try:
        yield tracker
    except Exception as e:
        tracker.success = False
        tracker.error_message = str(e)[: DisplayDefaults.ERROR_MESSAGE_MAX_LENGTH]
        raise
    finally:
        tracker._finalize()


@dataclass
class _OperationTracker:
    """Helper class for track_operation context manager."""

    tool_name: str
    operation_type: OperationType
    metadata: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error_message: Optional[str] = None
    files_processed: int = 0
    lines_analyzed: int = 0
    matches_found: int = 0
    _start_time: float = 0.0

    def _finalize(self) -> None:
        """Finalize and log the operation."""
        response_time_ms = int((time.perf_counter() - self._start_time) * ConversionFactors.MILLISECONDS_PER_SECOND)

        estimated_cost = calculate_operation_cost(
            self.operation_type,
            files_processed=self.files_processed,
            lines_analyzed=self.lines_analyzed,
            matches_found=self.matches_found,
        )

        entry = UsageLogEntry(
            tool_name=self.tool_name,
            operation_type=self.operation_type,
            success=self.success,
            error_message=self.error_message,
            response_time_ms=response_time_ms,
            estimated_cost=estimated_cost,
            files_processed=self.files_processed,
            lines_analyzed=self.lines_analyzed,
            matches_found=self.matches_found,
            metadata=self.metadata,
        )

        try:
            get_usage_database().log_usage(entry)
        except Exception as e:
            logger.error("usage_tracking_failed", error=str(e)[: DisplayDefaults.ERROR_OUTPUT_PREVIEW_LENGTH])


# =============================================================================
# Convenience Functions
# =============================================================================


def get_usage_stats(days: int = UsageTrackingDefaults.DEFAULT_STATS_LOOKBACK_DAYS) -> UsageStats:
    """Get usage statistics for the last N days.

    Args:
        days: Number of days to look back

    Returns:
        Usage statistics
    """
    start_time = datetime.now(UTC) - timedelta(days=days)
    return get_usage_database().get_stats(start_time=start_time)


def get_usage_alerts(thresholds: Optional[AlertThresholds] = None) -> List[UsageAlert]:
    """Get current usage alerts.

    Args:
        thresholds: Custom alert thresholds

    Returns:
        List of active alerts
    """
    return get_usage_database().get_alerts(thresholds)


def get_recent_usage(
    limit: int = UsageTrackingDefaults.DEFAULT_PAGINATION_LIMIT,
    tool_name: Optional[str] = None,
    success: Optional[bool] = None,
) -> List[UsageLogEntry]:
    """Get recent usage logs.

    Args:
        limit: Maximum entries to return
        tool_name: Filter by tool
        success: Filter by success status

    Returns:
        Recent usage log entries
    """
    return get_usage_database().get_recent_logs(
        limit=limit,
        tool_name=tool_name,
        success=success,
    )


def _format_report_header(stats: UsageStats) -> List[str]:
    sep = "=" * FormattingDefaults.USAGE_REPORT_WIDTH
    div = "-" * FormattingDefaults.SECTION_DIVIDER_WIDTH
    period = f"{stats.period_start.strftime('%Y-%m-%d %H:%M')} to {stats.period_end.strftime('%Y-%m-%d %H:%M')}"
    return [
        sep,
        "USAGE STATISTICS REPORT",
        sep,
        f"Period: {period}",
        "",
        "SUMMARY",
        div,
        f"Total Calls:      {stats.total_calls:,}",
        f"Successful:       {stats.successful_calls:,}",
        f"Failed:           {stats.failed_calls:,}",
        f"Success Rate:     {stats.success_rate:.1f}%",
        f"Total Cost:       {stats.total_cost:.6f} units",
        f"Average Cost:     {stats.average_cost:.6f} units",
        f"Avg Response:     {stats.average_response_time_ms:.0f}ms",
        "",
    ]


def format_usage_report(stats: UsageStats) -> str:
    """Format usage statistics as a human-readable report.

    Args:
        stats: Usage statistics to format

    Returns:
        Formatted report string
    """
    div = "-" * FormattingDefaults.SECTION_DIVIDER_WIDTH
    lines = _format_report_header(stats)

    if stats.calls_by_tool:
        lines.extend(["CALLS BY TOOL", div])
        for tool, count in sorted(stats.calls_by_tool.items(), key=lambda x: -x[1]):
            cost = stats.cost_by_tool.get(tool, 0.0)
            lines.append(f"  {tool}: {count:,} calls ({cost:.6f} units)")
        lines.append("")

    if stats.calls_by_operation:
        lines.extend(["CALLS BY OPERATION", div])
        for op, count in sorted(stats.calls_by_operation.items(), key=lambda x: -x[1]):
            lines.append(f"  {op}: {count:,}")
        lines.append("")

    lines.append("=" * FormattingDefaults.USAGE_REPORT_WIDTH)
    return "\n".join(lines)
