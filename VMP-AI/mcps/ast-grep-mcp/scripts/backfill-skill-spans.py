#!/usr/bin/env python3
"""Backfill OTEL plugin spans for a skill from existing agent invocation data.

Creates hook:plugin-pre-tool and hook:plugin-post-tool spans linked to
historical agent invocations, so the skill auditor recognizes usage history.

Usage:
    # Dry run (default) — prints spans to stdout
    python3 scripts/backfill-skill-spans.py --skill review --agent code-reviewer --category review

    # Write spans to trace JSONL files
    python3 scripts/backfill-skill-spans.py --skill review --agent code-reviewer --category review --write

    # Filter to a specific project
    python3 scripts/backfill-skill-spans.py --skill review --agent code-reviewer --category review --project ast-grep-mcp

    # Limit to specific sessions
    python3 scripts/backfill-skill-spans.py --skill review --agent code-reviewer --category review --sessions 7477d8dc,a3e2e2a5
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CLAUDE_DIR = Path.home() / ".claude"
TELEMETRY_DIR = CLAUDE_DIR / "telemetry"
AGENT_CACHE_DIR = CLAUDE_DIR / "agent-cache"
TRACE_CTX_DIR = TELEMETRY_DIR / "trace-ctx"
NS_PER_SECOND = 1_000_000_000
PRE_TOOL_DURATION_NS = 8_000_000  # 8ms synthetic pre-tool span duration

RESOURCE = {"serviceName": "claude-code-hooks", "serviceVersion": "1.0.0"}
BACKFILL_SOURCE = "backfill:agent-span-recovery"

# Agent log field indices and counts
# STARTED line format:  timestamp \t name \t category \t status \t STARTED \t flags
# COMPLETED line format: timestamp \t name \t COMPLETED[_*] \t Nbytes
SPAN_ID_BYTES = 8  # OTEL span ID width in bytes (hex-encoded)
LOG_MIN_FIELDS = 4  # minimum fields in a COMPLETED log line
LOG_STARTED_MIN_FIELDS = 5  # minimum fields to safely check the status field
LOG_STARTED_STATUS_IDX = 4  # index of "STARTED" token in STARTED lines
LOG_BYTES_FIELD_IDX = 3  # index of the Nbytes field in COMPLETED lines


def new_span_id() -> str:
    return secrets.token_hex(SPAN_ID_BYTES)


def iso_to_otel_time(iso_str: str) -> list[int]:
    """Convert ISO-8601 timestamp to OTEL [epoch_s, ns]."""
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    ts = dt.timestamp()
    epoch_s = int(ts)
    ns = int((ts - epoch_s) * NS_PER_SECOND)
    return [epoch_s, ns]


def load_trace_ctx(session_id: str) -> dict[str, Any] | None:
    """Load trace context for a session (try both full UUID and prefix match)."""
    # Try exact match first
    for f in TRACE_CTX_DIR.glob(f"{session_id}*.json"):
        try:
            result: dict[str, Any] = json.loads(f.read_text())
            return result
        except (json.JSONDecodeError, OSError):
            continue
    return None


def parse_agent_cache(agent_name: str, project_filter: str | None = None, session_filter: set[str] | None = None) -> list[dict[str, Any]]:
    """Parse agent-cache logs for invocations of a specific agent.

    Returns list of dicts with keys: session_id, started_at, completed_at,
    duration_s, output_bytes, status.
    """
    invocations: list[dict[str, Any]] = []

    for session_dir in AGENT_CACHE_DIR.iterdir():
        if not session_dir.is_dir():
            continue

        session_id = session_dir.name
        if session_filter and not any(session_id.startswith(s) for s in session_filter):
            continue

        # Filter by project name if requested (check session metadata)
        if project_filter:
            meta_file = session_dir / "session-metadata.json"
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text())
                    if project_filter not in meta.get("project", ""):
                        continue
                except (json.JSONDecodeError, OSError):
                    pass
            # else: no metadata — include session (cannot filter, do not drop)

        log_file = session_dir / "agent-invocations.log"
        if not log_file.exists():
            continue

        # Parse STARTED/COMPLETED pairs for the target agent
        # STARTED: timestamp \t name \t category \t status \t STARTED \t flags (6 fields)
        # COMPLETED: timestamp \t name \t COMPLETED[_*] \t Nbytes (4 fields)
        pending: dict[str, str] = {}  # agent_name -> started_iso
        for line in log_file.read_text().splitlines():
            parts = line.split("\t")
            if len(parts) < LOG_MIN_FIELDS:
                continue

            if len(parts) >= LOG_STARTED_MIN_FIELDS and parts[1] == agent_name and parts[LOG_STARTED_STATUS_IDX] == "STARTED":
                pending[agent_name] = parts[0]

            elif parts[1] == agent_name and parts[2].startswith("COMPLETED"):
                started_iso = pending.pop(agent_name, None)
                if started_iso is None:
                    continue

                output_bytes = 0
                if len(parts) > LOG_BYTES_FIELD_IDX and parts[LOG_BYTES_FIELD_IDX].endswith("bytes"):
                    try:
                        output_bytes = int(parts[LOG_BYTES_FIELD_IDX].replace("bytes", ""))
                    except ValueError:
                        pass

                invocations.append(
                    {
                        "session_id": session_id,
                        "started_at": started_iso,
                        "completed_at": parts[0],
                        "output_bytes": output_bytes,
                        "status": parts[2],
                    }
                )

    return invocations


def build_span(
    name: str,
    trace_id: str,
    session_id: str,
    start_time: list[int],
    end_time: list[int],
    duration: list[int],
    skill_name: str,
    agent_name: str,
    category: str,
    extra_attrs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a single OTEL-compatible span dict."""
    trigger = "PreToolUse" if "pre-tool" in name else "PostToolUse"
    attrs: dict[str, Any] = {
        "hook.name": name.replace("hook:", ""),
        "hook.type": "plugin",
        "session.id": session_id,
        "hook.trigger": trigger,
        "plugin.name": skill_name,
        "plugin.full_name": skill_name,
        "plugin.category": category,
        "plugin.source_type": "active",
        "agent.linked_type": agent_name,
        "backfill.source": BACKFILL_SOURCE,
        "backfill.timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if extra_attrs:
        attrs.update(extra_attrs)

    return {
        "traceId": trace_id,
        "spanId": new_span_id(),
        "name": name,
        "kind": 0,
        "startTime": start_time,
        "endTime": end_time,
        "duration": duration,
        "status": {"code": 1},
        "attributes": attrs,
        "events": [],
        "links": [],
        "resource": RESOURCE,
    }


def compute_duration(start: list[int], end: list[int]) -> list[int]:
    """Compute [seconds, nanoseconds] duration between two OTEL timestamps."""
    ds = end[0] - start[0]
    dns = end[1] - start[1]
    if dns < 0:
        ds -= 1
        dns += NS_PER_SECOND
    return [ds, dns]


def generate_spans(invocations: list[dict[str, Any]], skill_name: str, agent_name: str, category: str) -> list[tuple[str, dict[str, Any]]]:
    """Generate pre/post span pairs for each invocation.

    Returns list of (trace_date, span_dict) tuples for grouping by target file.
    """
    spans: list[tuple[str, dict[str, Any]]] = []

    for inv in invocations:
        ctx = load_trace_ctx(inv["session_id"])
        if ctx is None:
            print(f"  SKIP {inv['session_id'][:8]}: no trace-ctx", file=sys.stderr)
            continue

        trace_id = ctx["traceId"]
        start_time = iso_to_otel_time(inv["started_at"])
        end_time = iso_to_otel_time(inv["completed_at"])
        duration = compute_duration(start_time, end_time)

        # Derive trace date for file routing
        dt = datetime.fromisoformat(inv["started_at"].replace("Z", "+00:00"))
        trace_date = dt.strftime("%Y-%m-%d")

        # Pre-tool span (near-instant at start time)
        pre_end = [start_time[0], start_time[1] + PRE_TOOL_DURATION_NS]
        if pre_end[1] >= NS_PER_SECOND:
            pre_end = [pre_end[0] + 1, pre_end[1] - NS_PER_SECOND]

        pre_span = build_span(
            "hook:plugin-pre-tool",
            trace_id,
            inv["session_id"],
            start_time,
            pre_end,
            [0, PRE_TOOL_DURATION_NS],
            skill_name,
            agent_name,
            category,
            {"plugin.has_args": True},
        )
        spans.append((trace_date, pre_span))

        # Post-tool span (full duration)
        post_span = build_span(
            "hook:plugin-post-tool",
            trace_id,
            inv["session_id"],
            start_time,
            end_time,
            duration,
            skill_name,
            agent_name,
            category,
            {
                "plugin.has_args": True,
                "agent.output_bytes": inv["output_bytes"],
                "agent.completion_status": inv["status"],
            },
        )
        spans.append((trace_date, post_span))

    return spans


def check_already_backfilled(trace_file: Path, skill_name: str) -> set[str]:
    """Return set of session IDs already backfilled for this skill in a trace file."""
    existing: set[str] = set()
    if not trace_file.exists():
        return existing
    for line in trace_file.read_text().splitlines():
        try:
            span = json.loads(line)
            attrs = span.get("attributes", {})
            if attrs.get("backfill.source") == BACKFILL_SOURCE and attrs.get("plugin.name") == skill_name:
                existing.add(attrs.get("session.id", ""))
        except json.JSONDecodeError:
            continue
    return existing


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill OTEL plugin spans for a skill")
    parser.add_argument("--skill", required=True, help="Skill name to backfill (e.g. 'review')")
    parser.add_argument("--agent", required=True, help="Source agent name (e.g. 'code-reviewer')")
    parser.add_argument("--category", required=True, help="Skill category (e.g. 'review', 'analysis')")
    parser.add_argument("--project", default=None, help="Filter to sessions for this project name")
    parser.add_argument("--sessions", default=None, help="Comma-separated session ID prefixes")
    parser.add_argument("--write", action="store_true", help="Write spans to trace files (default: dry run)")
    args = parser.parse_args()

    session_filter = set(args.sessions.split(",")) if args.sessions else None

    print(f"Scanning agent-cache for '{args.agent}' invocations...", file=sys.stderr)
    invocations = parse_agent_cache(args.agent, args.project, session_filter)
    print(f"Found {len(invocations)} invocations across {len({i['session_id'] for i in invocations})} sessions", file=sys.stderr)

    if not invocations:
        print("No invocations found. Nothing to backfill.", file=sys.stderr)
        sys.exit(0)

    spans = generate_spans(invocations, args.skill, args.agent, args.category)
    print(f"Generated {len(spans)} spans ({len(spans) // 2} invocations)", file=sys.stderr)

    # Group spans by target trace file
    by_file: dict[str, list[dict[str, Any]]] = {}
    for trace_date, span in spans:
        fname = f"traces-{trace_date}.jsonl"
        by_file.setdefault(fname, []).append(span)

    if not args.write:
        print("\n--- DRY RUN (pass --write to append to trace files) ---\n", file=sys.stderr)
        for fname, file_spans in sorted(by_file.items()):
            print(f"# Would append {len(file_spans)} spans to {fname}", file=sys.stderr)
            for span in file_spans:
                print(json.dumps(span))
        print(f"\nTotal: {len(spans)} spans to {len(by_file)} files", file=sys.stderr)
        return

    # Write mode — append with idempotency check
    total_written = 0
    total_skipped = 0
    for fname, file_spans in sorted(by_file.items()):
        trace_file = TELEMETRY_DIR / fname
        already = check_already_backfilled(trace_file, args.skill)

        new_spans = [s for s in file_spans if s["attributes"]["session.id"] not in already]
        skipped = len(file_spans) - len(new_spans)
        total_skipped += skipped

        if not new_spans:
            print(f"  {fname}: all {len(file_spans)} spans already exist, skipping", file=sys.stderr)
            continue

        with open(trace_file, "a") as f:
            for span in new_spans:
                f.write(json.dumps(span) + "\n")
        total_written += len(new_spans)
        print(f"  {fname}: appended {len(new_spans)} spans ({skipped} skipped as duplicates)", file=sys.stderr)

    print(f"\nDone: wrote {total_written} spans, skipped {total_skipped} duplicates", file=sys.stderr)


if __name__ == "__main__":
    main()
