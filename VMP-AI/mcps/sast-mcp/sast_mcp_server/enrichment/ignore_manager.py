"""Manage ignored SAST findings with atomic persistence."""

import json
import logging
import os
import tempfile
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class IgnoreManager:
    """Manages a per-project ignore list for SAST findings.

    The ignore list is stored as `.sast-mcp-ignore.json` in the target project
    directory. Each entry maps a finding hash to metadata about why it was ignored.
    """

    def __init__(self, target_path: str):
        self.ignore_file = os.path.join(target_path, ".sast-mcp-ignore.json")
        self._load()

    def _load(self) -> None:
        """Load the ignore file from disk."""
        self.ignored_hashes: dict[str, dict] = {}
        if os.path.exists(self.ignore_file):
            try:
                with open(self.ignore_file, encoding="utf-8") as f:
                    data = json.load(f)
                # Support both old format (hash -> reason string) and new format (hash -> dict)
                for key, value in data.items():
                    if isinstance(value, str):
                        # Migrate old format
                        self.ignored_hashes[key] = {
                            "reason": value,
                            "ignored_at": "unknown",
                        }
                    elif isinstance(value, dict):
                        self.ignored_hashes[key] = value
                    else:
                        self.ignored_hashes[key] = {"reason": str(value), "ignored_at": "unknown"}
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Could not load ignore file %s: %s", self.ignore_file, e)

    def _save(self) -> None:
        """Atomically write the ignore file to prevent corruption.

        Uses write-to-temp-then-rename pattern so a crash mid-write
        won't corrupt the existing file.
        """
        dir_path = os.path.dirname(self.ignore_file)
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=dir_path, prefix=".sast-ignore-", suffix=".tmp"
            )
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.ignored_hashes, f, indent=4, sort_keys=True)
            os.replace(tmp_path, self.ignore_file)
        except OSError as e:
            logger.error("Failed to save ignore file: %s", e)
            # Clean up temp file if it exists
            if "tmp_path" in locals() and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def is_ignored(self, finding_hash: str) -> bool:
        """Check if a finding hash is in the ignore list."""
        return finding_hash in self.ignored_hashes

    def ignore(self, finding_hash: str, reason: str = "") -> None:
        """Add a finding to the ignore list.

        Args:
            finding_hash: The unique hash of the finding to ignore.
            reason: Optional justification for ignoring.
        """
        self.ignored_hashes[finding_hash] = {
            "reason": reason,
            "ignored_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save()
        logger.info("Ignored finding %s (reason: %s)", finding_hash[:12], reason or "none")

    def unignore(self, finding_hash: str) -> bool:
        """Remove a finding from the ignore list.

        Args:
            finding_hash: The hash to remove.

        Returns:
            True if the hash was found and removed, False if it wasn't ignored.
        """
        if finding_hash in self.ignored_hashes:
            del self.ignored_hashes[finding_hash]
            self._save()
            logger.info("Unignored finding %s", finding_hash[:12])
            return True
        return False

    def list_ignored(self) -> list[dict[str, str]]:
        """Return all currently ignored findings with their metadata.

        Returns:
            List of dicts with 'hash', 'reason', and 'ignored_at' keys.
        """
        return [
            {"hash": h, **meta}
            for h, meta in self.ignored_hashes.items()
        ]
