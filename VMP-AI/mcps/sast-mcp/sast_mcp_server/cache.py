"""Scan result caching and baseline comparison.

Stores scan results in `.sast-mcp-cache/` within the target project directory.
Supports named baselines (tags) for trend analysis and regression detection.
"""

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from glob import glob

from sast_mcp_server.config import get_settings
from sast_mcp_server.models import Finding, SeverityLevel

logger = logging.getLogger(__name__)

# Files/dirs ignored when fingerprinting a target for incremental scans.
_FINGERPRINT_SKIP_DIRS = {
    ".git", ".sast-mcp-cache",
    "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache",
    ".pytest_cache", "dist", "build", ".tox",
}


def compute_target_fingerprint(target_path: str) -> str:
    """Return a hash of the target's source files (path + size + mtime).

    Used for incremental scans: if the fingerprint matches a cached scan, the
    files haven't changed and the cached findings can be reused. Best-effort —
    skips common vendored/build directories and unreadable files.
    """
    target_path = os.path.abspath(target_path)
    if os.path.isfile(target_path):
        try:
            st = os.stat(target_path)
            payload = f"{target_path}:{st.st_size}:{int(st.st_mtime)}"
        except OSError:
            payload = target_path
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    parts: list[str] = []
    for root, dirs, files in os.walk(target_path):
        dirs[:] = sorted(d for d in dirs if d not in _FINGERPRINT_SKIP_DIRS)
        for name in sorted(files):
            fp = os.path.join(root, name)
            try:
                st = os.stat(fp)
            except OSError:
                continue
            rel = os.path.relpath(fp, target_path).replace("\\", "/")
            parts.append(f"{rel}:{st.st_size}:{int(st.st_mtime)}")
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return digest

# Default cache TTL: 24 hours (from validated central config)
DEFAULT_CACHE_TTL = get_settings().cache_ttl

# Max number of non-tagged (timestamped) scans to retain (0 = unlimited).
DEFAULT_CACHE_MAX_SCANS = get_settings().cache_max_scans

CACHE_DIR_NAME = ".sast-mcp-cache"


def _atomic_write_json(path: str, data: dict) -> None:
    """Write JSON to ``path`` atomically (temp file + os.replace).

    Prevents readers from observing a half-written cache file when scans run
    concurrently against the same project.
    """
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


@dataclass
class CachedScanMeta:
    """Lightweight metadata about a cached scan (no findings loaded)."""

    cache_id: str
    scanner: str
    timestamp: str
    tag: str | None
    target_path: str
    finding_count: int
    min_severity: str
    duration_ms: int


@dataclass
class CachedScan:
    """A full cached scan result with findings."""

    cache_id: str
    scanner: str
    timestamp: str
    tag: str | None
    target_path: str
    finding_count: int
    min_severity: str
    duration_ms: int
    findings: list[Finding]
    fingerprint: str = ""


@dataclass
class ScanDiff:
    """Difference between a baseline scan and the current scan."""

    new_findings: list[Finding] = field(default_factory=list)
    fixed_findings: list[Finding] = field(default_factory=list)
    unchanged_findings: list[Finding] = field(default_factory=list)
    baseline_total: int = 0
    current_total: int = 0
    severity_trend: dict[str, dict[str, int]] = field(default_factory=dict)


class ScanCache:
    """Manages cached scan results for a target project.

    Storage layout:
        <target_path>/.sast-mcp-cache/
            <scanner>_<timestamp>.json       # Timestamped scan
            <scanner>_tag_<tagname>.json      # Named baseline
    """

    def __init__(self, target_path: str):
        self.target_path = os.path.abspath(target_path)
        self.cache_dir = os.path.join(self.target_path, CACHE_DIR_NAME)

    def _ensure_dir(self) -> None:
        """Create the cache directory if it doesn't exist."""
        os.makedirs(self.cache_dir, exist_ok=True)

    def save_scan(
        self,
        scanner_name: str,
        findings: list[Finding],
        tag: str | None = None,
        min_severity: str = "LOW",
        duration_ms: int = 0,
        fingerprint: str = "",
    ) -> str:
        """Save scan results to cache.

        Args:
            scanner_name: The scanner that produced the findings.
            findings: List of Finding objects to cache.
            tag: Optional named tag (e.g., 'main', 'pre-release').
            min_severity: The minimum severity filter used.
            duration_ms: How long the scan took in milliseconds.
            fingerprint: Optional target fingerprint for incremental-scan reuse.

        Returns:
            The cache ID of the saved scan.
        """
        self._ensure_dir()

        timestamp = datetime.now(timezone.utc).isoformat()
        ts_slug = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        cache_id = f"{scanner_name}_{ts_slug}"

        scan_data = {
            "cache_id": cache_id,
            "scanner": scanner_name,
            "timestamp": timestamp,
            "tag": tag,
            "target_path": self.target_path,
            "finding_count": len(findings),
            "min_severity": min_severity,
            "duration_ms": duration_ms,
            "fingerprint": fingerprint,
            "findings": [f.to_dict() for f in findings],
        }

        # Always save timestamped file (atomically)
        ts_file = os.path.join(self.cache_dir, f"{cache_id}.json")
        _atomic_write_json(ts_file, scan_data)
        logger.info("Cached scan %s (%d findings)", cache_id, len(findings))

        # If tagged, also save/overwrite the tag file
        if tag:
            tag_file = os.path.join(
                self.cache_dir, f"{scanner_name}_tag_{tag}.json"
            )
            _atomic_write_json(tag_file, scan_data)
            logger.info("Saved baseline tag '%s' for %s", tag, scanner_name)

        # Opportunistically keep the cache directory bounded.
        self.cleanup_expired()
        self.enforce_max_scans()

        return cache_id

    def enforce_max_scans(self, max_scans: int = DEFAULT_CACHE_MAX_SCANS) -> int:
        """Prune oldest non-tagged scans so at most ``max_scans`` remain.

        Tagged baselines are never pruned. ``max_scans <= 0`` disables the cap.

        Returns:
            Number of files removed.
        """
        if max_scans <= 0 or not os.path.exists(self.cache_dir):
            return 0

        # Newest first; tagged baselines are exempt.
        timestamped = [
            fp
            for fp in glob(os.path.join(self.cache_dir, "*.json"))
            if "_tag_" not in os.path.basename(fp)
        ]
        timestamped.sort(key=os.path.getmtime, reverse=True)

        removed = 0
        for filepath in timestamped[max_scans:]:
            try:
                os.remove(filepath)
                removed += 1
            except OSError as e:
                logger.warning("Could not prune %s: %s", filepath, e)
        if removed:
            logger.info("Pruned %d cache files over the %d cap", removed, max_scans)
        return removed

    def load_latest(self, scanner_name: str) -> CachedScan | None:
        """Load the most recent cached scan for a scanner.

        Args:
            scanner_name: Scanner name to look up.

        Returns:
            CachedScan or None if no cached scan exists.
        """
        pattern = os.path.join(
            self.cache_dir, f"{scanner_name}_2*.json"
        )
        files = sorted(glob(pattern), reverse=True)
        if not files:
            return None
        return self._load_file(files[0])

    def load_fresh(self, scanner_name: str, fingerprint: str) -> CachedScan | None:
        """Return the latest cached scan iff its fingerprint matches.

        Powers incremental scans: a non-empty matching fingerprint means the
        target's files are unchanged since that scan, so its findings are reused
        instead of re-running the scanner.
        """
        if not fingerprint:
            return None
        latest = self.load_latest(scanner_name)
        if latest is not None and latest.fingerprint == fingerprint:
            return latest
        return None

    def load_by_tag(self, scanner_name: str, tag: str) -> CachedScan | None:
        """Load a named baseline scan.

        Args:
            scanner_name: Scanner name.
            tag: The baseline tag name.

        Returns:
            CachedScan or None if no baseline with that tag exists.
        """
        tag_file = os.path.join(
            self.cache_dir, f"{scanner_name}_tag_{tag}.json"
        )
        if not os.path.exists(tag_file):
            return None
        return self._load_file(tag_file)

    def list_scans(
        self, scanner_name: str | None = None
    ) -> list[CachedScanMeta]:
        """List all cached scans, optionally filtered by scanner.

        Args:
            scanner_name: If provided, only list scans from this scanner.

        Returns:
            List of CachedScanMeta objects, newest first.
        """
        if not os.path.exists(self.cache_dir):
            return []

        if scanner_name:
            pattern = os.path.join(self.cache_dir, f"{scanner_name}_*.json")
        else:
            pattern = os.path.join(self.cache_dir, "*.json")

        results: list[CachedScanMeta] = []
        for filepath in sorted(glob(pattern), reverse=True):
            try:
                with open(filepath, encoding="utf-8") as f:
                    data = json.load(f)
                results.append(
                    CachedScanMeta(
                        cache_id=data.get("cache_id", ""),
                        scanner=data.get("scanner", ""),
                        timestamp=data.get("timestamp", ""),
                        tag=data.get("tag"),
                        target_path=data.get("target_path", ""),
                        finding_count=data.get("finding_count", 0),
                        min_severity=data.get("min_severity", "LOW"),
                        duration_ms=data.get("duration_ms", 0),
                    )
                )
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Could not read cache file %s: %s", filepath, e)

        return results

    def find_finding_by_hash(self, finding_hash: str) -> Finding | None:
        """Search all cached scans for a finding with the given hash.

        Used to recover full finding details (file, line, context) for a hash
        that an agent surfaced from an earlier scan, without re-scanning.

        Args:
            finding_hash: The finding hash to look up.

        Returns:
            The first matching Finding, or None if no cached scan contains it.
        """
        if not os.path.exists(self.cache_dir):
            return None

        # Newest scans first so the freshest copy of a finding wins.
        for filepath in sorted(glob(os.path.join(self.cache_dir, "*.json")), reverse=True):
            scan = self._load_file(filepath)
            if scan is None:
                continue
            for finding in scan.findings:
                if finding.finding_hash == finding_hash:
                    return finding
        return None

    def compare(
        self, baseline: CachedScan, current_findings: list[Finding]
    ) -> ScanDiff:
        """Compare current findings against a baseline scan.

        Args:
            baseline: The baseline CachedScan to compare against.
            current_findings: Current list of findings.

        Returns:
            ScanDiff with new, fixed, and unchanged findings.
        """
        baseline_hashes = {f.finding_hash: f for f in baseline.findings}
        current_hashes = {f.finding_hash: f for f in current_findings}

        new_findings = [
            f for h, f in current_hashes.items()
            if h not in baseline_hashes
        ]
        fixed_findings = [
            f for h, f in baseline_hashes.items()
            if h not in current_hashes
        ]
        unchanged_findings = [
            f for h, f in current_hashes.items()
            if h in baseline_hashes
        ]

        # Compute severity trend
        severity_trend: dict[str, dict[str, int]] = {}
        for level in SeverityLevel:
            baseline_count = sum(
                1 for f in baseline.findings if f.severity == level
            )
            current_count = sum(
                1 for f in current_findings if f.severity == level
            )
            severity_trend[level.value] = {
                "baseline": baseline_count,
                "current": current_count,
                "delta": current_count - baseline_count,
            }

        return ScanDiff(
            new_findings=new_findings,
            fixed_findings=fixed_findings,
            unchanged_findings=unchanged_findings,
            baseline_total=len(baseline.findings),
            current_total=len(current_findings),
            severity_trend=severity_trend,
        )

    def cleanup_expired(self, ttl: int = DEFAULT_CACHE_TTL) -> int:
        """Remove cached scans older than the TTL.

        Args:
            ttl: Time-to-live in seconds. Default from SAST_MCP_CACHE_TTL.

        Returns:
            Number of files removed.
        """
        if not os.path.exists(self.cache_dir):
            return 0

        now = time.time()
        removed = 0
        for filepath in glob(os.path.join(self.cache_dir, "*.json")):
            # Don't remove tagged baselines
            basename = os.path.basename(filepath)
            if "_tag_" in basename:
                continue

            try:
                mtime = os.path.getmtime(filepath)
                if now - mtime > ttl:
                    os.remove(filepath)
                    removed += 1
                    logger.debug("Removed expired cache: %s", basename)
            except OSError as e:
                logger.warning("Could not remove %s: %s", filepath, e)

        if removed:
            logger.info("Cleaned up %d expired cache files", removed)
        return removed

    def _load_file(self, filepath: str) -> CachedScan | None:
        """Load a single cache file into a CachedScan object."""
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Could not load cache file %s: %s", filepath, e)
            return None

        findings = []
        for fd in data.get("findings", []):
            try:
                findings.append(
                    Finding(
                        scanner=fd.get("scanner", ""),
                        title=fd.get("title", ""),
                        message=fd.get("message", ""),
                        file=fd.get("file", ""),
                        line_start=fd.get("line_start", 1),
                        line_end=fd.get("line_end", 1),
                        severity=SeverityLevel(
                            fd.get("severity", "MEDIUM")
                        ),
                        confidence=_parse_confidence(
                            fd.get("confidence", "MEDIUM")
                        ),
                        context=fd.get("context", ""),
                        finding_hash=fd.get("finding_hash", ""),
                        language=fd.get("language", ""),
                        cwe=fd.get("cwe", ""),
                        cvss_score=fd.get("cvss_score"),
                        cvss_vector=fd.get("cvss_vector", ""),
                        owasp_category=fd.get("owasp_category", ""),
                        references=fd.get("references", []),
                        remediation=fd.get("remediation", ""),
                    )
                )
            except (ValueError, KeyError) as e:
                logger.warning("Skipping malformed cached finding: %s", e)

        return CachedScan(
            cache_id=data.get("cache_id", ""),
            scanner=data.get("scanner", ""),
            timestamp=data.get("timestamp", ""),
            tag=data.get("tag"),
            target_path=data.get("target_path", ""),
            finding_count=data.get("finding_count", 0),
            min_severity=data.get("min_severity", "LOW"),
            duration_ms=data.get("duration_ms", 0),
            findings=findings,
            fingerprint=data.get("fingerprint", ""),
        )


def _parse_confidence(value: str):
    """Parse a confidence string to enum, defaulting to MEDIUM."""
    from sast_mcp_server.models import ConfidenceLevel

    try:
        return ConfidenceLevel(value.upper())
    except (ValueError, AttributeError):
        return ConfidenceLevel.MEDIUM
