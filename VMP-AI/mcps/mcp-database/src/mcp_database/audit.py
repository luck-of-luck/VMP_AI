from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .formatter import json_default, sanitize_error

DEFAULT_AUDIT_PATH = Path.home() / ".local" / "state" / "mcp-database" / "audit.log"

AUDIT_SCHEMA_VERSION = 1
_TAIL_BYTES = 65536


def _line_hash(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def _last_line(path: Path) -> str | None:
    """The last non-empty line of the log, reading only the file's tail."""
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        handle.seek(max(0, size - _TAIL_BYTES))
        lines = handle.read().splitlines()
    for raw in reversed(lines):
        if raw.strip():
            return raw.decode("utf-8")
    return None


def verify_chain(path: Path) -> int | None:
    """Index of the first entry whose hash link is broken, or None when the whole chain is intact."""
    expected = ""
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        if json.loads(line).get("prev") != expected:
            return index
        expected = _line_hash(line)
    return None


class AuditLogger:
    """Append-only JSONL log of every write_/admin_ call and every export (query shapes, never raw values).

    Entries are hash-chained: each carries `prev`, the sha256 of the previous line, so any
    edit or deletion in the middle of the log breaks every link after it (see verify_chain).
    """

    def __init__(self, path: Path | None = None, *, max_bytes: int | None = None) -> None:
        self.path = path or DEFAULT_AUDIT_PATH
        self.max_bytes = max_bytes
        self._lock = threading.Lock()
        self._last_hash: str | None = None

    def _rotate_if_needed(self) -> None:
        """Roll audit.log to audit.log.1 once it passes max_bytes; the new file restarts the hash chain."""
        if self.max_bytes is None or not self.path.exists():
            return
        if self.path.stat().st_size < self.max_bytes:
            return
        self.path.replace(self.path.with_suffix(self.path.suffix + ".1"))
        self._last_hash = ""

    def _chain_tail(self) -> str:
        """The hash of the last line already on disk, resuming the chain across restarts."""
        if self._last_hash is None:
            line = _last_line(self.path) if self.path.exists() else None
            self._last_hash = _line_hash(line) if line is not None else ""
        return self._last_hash

    def record(
        self,
        *,
        connection: str,
        tool: str,
        query: Any,
        ok: bool,
        dry_run: bool = False,
        affected: int | None = None,
        duration_ms: float | None = None,
        error: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        """Write one chained audit entry; creates the file 0600 on first use, redacts passwords in error text."""
        entry: dict[str, Any] = {
            "v": AUDIT_SCHEMA_VERSION,
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "connection": connection,
            "tool": tool,
            "query": query,
            "ok": ok,
            "dry_run": dry_run,
        }
        if detail:
            entry.update(detail)
        if affected is not None:
            entry["affected"] = affected
        if duration_ms is not None:
            entry["duration_ms"] = round(duration_ms, 1)
        if error:
            entry["error"] = sanitize_error(error)

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._rotate_if_needed()
            entry["prev"] = self._chain_tail()
            line = json.dumps(entry, default=json_default, ensure_ascii=False)
            created = not self.path.exists()
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
            self._last_hash = _line_hash(line)
        if created:
            os.chmod(self.path, 0o600)
