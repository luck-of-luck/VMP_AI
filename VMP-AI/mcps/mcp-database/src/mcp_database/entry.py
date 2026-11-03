from __future__ import annotations

import logging
import os
import signal
import sys
from pathlib import Path

from .audit import AuditLogger
from .config import connection_from_env
from .errors import ConfigError
from .server import build_server
from .tool_names import resolve_enabled_tools

LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


def _install_graceful_shutdown() -> None:
    """Make SIGTERM behave like Ctrl-C so the server's lifespan runs and connection pools close cleanly."""
    try:
        signal.signal(signal.SIGTERM, signal.default_int_handler)
    except ValueError:
        pass  # not the main thread (e.g. under a test harness); nothing to install


def main() -> None:
    """Serve one connection per instance, configured entirely via environment variables."""
    level = (os.environ.get("LOG_LEVEL") or "INFO").upper()
    if level not in LOG_LEVELS:
        print(f"mcp-database: LOG_LEVEL must be one of: {', '.join(LOG_LEVELS)}", file=sys.stderr)
        raise SystemExit(2)
    logging.basicConfig(level=level, stream=sys.stderr, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    try:
        cfg = connection_from_env()
        enabled_tools = resolve_enabled_tools(os.environ)
    except ConfigError as exc:
        print(f"mcp-database: {exc}", file=sys.stderr)
        raise SystemExit(2) from None

    audit_path = os.environ.get("AUDIT_LOG")
    max_bytes_raw = os.environ.get("AUDIT_MAX_BYTES")
    try:
        max_bytes = int(max_bytes_raw) if max_bytes_raw else None
    except ValueError:
        print(f"mcp-database: AUDIT_MAX_BYTES must be an integer, got {max_bytes_raw!r}", file=sys.stderr)
        raise SystemExit(2) from None
    logging.getLogger("mcp_database").info("Serving connection '%s' (%s, %s)", cfg.name, cfg.type, cfg.access_mode)
    audit = AuditLogger(Path(audit_path) if audit_path else None, max_bytes=max_bytes)
    _install_graceful_shutdown()
    build_server({cfg.name: cfg}, audit=audit, enabled_tools=enabled_tools).run()
