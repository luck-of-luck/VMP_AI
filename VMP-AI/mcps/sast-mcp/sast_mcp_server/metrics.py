"""Lightweight in-process metrics with a Prometheus text exposition.

No external dependency: we keep simple counters/observations in module-level
dicts (guarded by a lock) and render them in the Prometheus text format on
demand for the ``/metrics`` endpoint. This is deliberately minimal — enough for
liveness dashboards and alerting without pulling in a metrics client.

Instrumentation happens in one place each: the ``audited`` tool wrapper
(``server.py``) records every tool call, and ``aggregator.run_all_scanners``
records scan durations and errors.
"""

import threading
import time
from dataclasses import dataclass, field

_lock = threading.Lock()

# Counters keyed by a sorted-label tuple.
_counters: dict[str, dict[tuple[tuple[str, str], ...], float]] = {}
# Histograms: store count + sum to expose _count/_sum (good enough for averages).
_summaries: dict[str, dict[tuple[tuple[str, str], ...], "_SummaryValue"]] = {}

_START_TIME = time.time()


@dataclass
class _SummaryValue:
    count: int = 0
    total: float = 0.0


# Metric metadata for HELP/TYPE lines.
_HELP: dict[str, tuple[str, str]] = {
    "sast_tool_calls_total": ("counter", "Total MCP tool invocations."),
    "sast_scans_total": ("counter", "Total scanner runs via run_all_scanners."),
    "sast_scan_errors_total": ("counter", "Scanner runs that raised an error."),
    "sast_findings_total": ("counter", "Findings returned (post-dedup)."),
    "sast_scan_duration_seconds": ("summary", "Aggregate multi-scanner scan duration."),
    "sast_tool_duration_seconds": ("summary", "Per-tool execution duration."),
}


def _key(labels: dict[str, str] | None) -> tuple[tuple[str, str], ...]:
    if not labels:
        return ()
    return tuple(sorted(labels.items()))


def inc(name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
    """Increment a counter."""
    with _lock:
        series = _counters.setdefault(name, {})
        series[_key(labels)] = series.get(_key(labels), 0.0) + value


def observe(name: str, value: float, labels: dict[str, str] | None = None) -> None:
    """Record an observation into a summary (count + sum)."""
    with _lock:
        series = _summaries.setdefault(name, {})
        sv = series.setdefault(_key(labels), _SummaryValue())
        sv.count += 1
        sv.total += value


def reset() -> None:
    """Clear all metrics (used by tests)."""
    with _lock:
        _counters.clear()
        _summaries.clear()


def _format_labels(key: tuple[tuple[str, str], ...]) -> str:
    if not key:
        return ""
    inner = ",".join(f'{k}="{_escape(v)}"' for k, v in key)
    return "{" + inner + "}"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def render_prometheus() -> str:
    """Render all metrics in the Prometheus text exposition format."""
    lines: list[str] = []
    with _lock:
        # Process uptime is always useful.
        lines.append("# HELP sast_uptime_seconds Seconds since server start.")
        lines.append("# TYPE sast_uptime_seconds gauge")
        lines.append(f"sast_uptime_seconds {time.time() - _START_TIME:.3f}")

        for name, series in sorted(_counters.items()):
            mtype, help_text = _HELP.get(name, ("counter", ""))
            lines.append(f"# HELP {name} {help_text}")
            lines.append(f"# TYPE {name} {mtype}")
            for key, value in sorted(series.items()):
                lines.append(f"{name}{_format_labels(key)} {value:g}")

        for name, summ in sorted(_summaries.items()):
            _mtype, help_text = _HELP.get(name, ("summary", ""))
            lines.append(f"# HELP {name} {help_text}")
            lines.append(f"# TYPE {name} summary")
            for key, sv in sorted(summ.items()):
                labels = _format_labels(key)
                lines.append(f"{name}_count{labels} {sv.count:g}")
                lines.append(f"{name}_sum{labels} {sv.total:g}")

    return "\n".join(lines) + "\n"


@dataclass
class _Snapshot:
    counters: dict = field(default_factory=dict)
    summaries: dict = field(default_factory=dict)


def snapshot() -> _Snapshot:
    """Return a copy of current metric values (used by tests/ready endpoint)."""
    with _lock:
        return _Snapshot(
            counters={n: dict(s) for n, s in _counters.items()},
            summaries={
                n: {k: (v.count, v.total) for k, v in s.items()}
                for n, s in _summaries.items()
            },
        )
