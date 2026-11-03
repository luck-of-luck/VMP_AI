"""SAST MCP Server — Static Application Security Testing for AI agents.

Exposes SAST scanners (Bandit, njsscan, Bearer, Semgrep, Trivy, CodeQL, Checkov)
as MCP tools that can be invoked by any MCP-compatible AI agent
(Gemini CLI, Claude, OpenAI, Cursor, etc.).

Supports stdio (local), SSE (legacy), and streamable-http (production) transports.
Optional JWT / API key authentication for remote deployments.
"""

import argparse
import asyncio
import functools
import json
import logging
import os
import sys
import time
import warnings
from collections.abc import Awaitable, Callable

from fastmcp import FastMCP

from sast_mcp_server import __version__, metrics
from sast_mcp_server.aggregator import run_all_scanners
from sast_mcp_server.auth import (
    SCOPE_CONFIG_WRITE,
    SCOPE_SCAN_READ,
    SCOPE_SCAN_WRITE,
    AuthError,
    AuthProvider,
    authorize,
)
from sast_mcp_server.cache import ScanCache, compute_target_fingerprint
from sast_mcp_server.config import get_settings
from sast_mcp_server.enrichment.git_diff import get_modified_files
from sast_mcp_server.enrichment.ignore_manager import IgnoreManager
from sast_mcp_server.enrichment.patch_apply import apply_unified_diff
from sast_mcp_server.enrichment.patch_prompt import build_patch_prompt
from sast_mcp_server.integrations import IntegrationError
from sast_mcp_server.integrations.defectdojo import upload_to_defectdojo as _dd_upload
from sast_mcp_server.integrations.github import comment_on_pull_request as _gh_comment
from sast_mcp_server.integrations.github import upload_to_github as _gh_upload
from sast_mcp_server.integrations.gitlab import comment_on_merge_request as _gl_comment
from sast_mcp_server.integrations.jira import create_jira_issue as _jira_create
from sast_mcp_server.integrations.slack import notify_slack as _slack_notify
from sast_mcp_server.integrations.teams import notify_teams as _teams_notify
from sast_mcp_server.models import SEVERITY_ORDER, ConfidenceLevel, SeverityLevel
from sast_mcp_server.prompts import register_prompts
from sast_mcp_server.ratelimit import RateLimiter
from sast_mcp_server.reporting import (
    PdfUnavailableError,
    compliance_to_markdown,
    findings_to_compliance,
    findings_to_cyclonedx,
    findings_to_html,
    findings_to_pdf,
    findings_to_spdx,
    pdf_available,
    syft_cyclonedx_components,
)
from sast_mcp_server.reporting.vex import (
    SUPPRESSING_DISPOSITIONS,
    build_vex_statement,
    findings_to_vex,
    normalize_disposition,
)
from sast_mcp_server.resources import register_resources
from sast_mcp_server.sarif import findings_to_sarif, parse_sarif
from sast_mcp_server.scanners.factory import SCANNER_INFO, ScannerFactory

# ---------------------------------------------------------------------------
# Logging — MUST go to stderr so stdout stays clean for MCP stdio transport
# ---------------------------------------------------------------------------
settings = get_settings()
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("sast_mcp_server")

# Configurable scan timeout (seconds)
SCAN_TIMEOUT = settings.scan_timeout

# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "SAST_MCP_Server",
    version=__version__,
    instructions=(
        "Static Application Security Testing (SAST) server. "
        "Scan code for vulnerabilities using Bandit (Python), "
        "njsscan (JavaScript), Bearer (multi-language), Semgrep (30+ languages), "
        "Trivy (vulnerabilities, secrets, IaC), CodeQL (deep semantic analysis), "
        "or Checkov (IaC policy checks). "
        "Use scan_all to run all installed scanners at once with deduplication. "
        "Use save_baseline/compare_baseline for trend analysis. "
        "Push results to dashboards with upload_to_defectdojo / upload_to_github. "
        "Use generate_fix_prompt + apply_patch to remediate findings as diffs. "
        "MCP Resources provide read-only security dashboards. "
        "MCP Prompts provide pre-built security workflows."
    ),
)

# Register MCP Resources and Prompts
register_resources(mcp)
register_prompts(mcp)


# ---------------------------------------------------------------------------
# Scanner readiness (cached)
# ---------------------------------------------------------------------------
# Probing a scanner's check_dependency() spawns a subprocess (e.g. `bandit
# --version`). Doing that for all 11 scanners on every /ready poll is far too
# expensive — under load it serializes behind subprocess spawns and tanks
# latency. Scanner availability is effectively static for a process's lifetime,
# so cache the probe result for a short TTL.
_READINESS_TTL = 15.0
_readiness_cache: tuple[float, list[str]] | None = None
_readiness_lock = asyncio.Lock()


async def _probe_installed_scanners() -> list[str]:
    """Probe every scanner's ``check_dependency()``; return installed names."""
    installed: list[str] = []
    for name in ScannerFactory.list_scanners():
        try:
            await ScannerFactory.get_scanner(name).check_dependency()
            installed.append(name)
        except Exception:
            pass
    return sorted(installed)


async def _installed_scanners(use_cache: bool = True, ttl: float = _READINESS_TTL) -> list[str]:
    """Installed-scanner names, cached for ``ttl`` seconds to keep /ready cheap."""
    global _readiness_cache
    if use_cache and _readiness_cache is not None:
        ts, names = _readiness_cache
        if (time.monotonic() - ts) < ttl:
            return names
    async with _readiness_lock:
        # Re-check after acquiring the lock — another caller may have refreshed.
        if use_cache and _readiness_cache is not None:
            ts, names = _readiness_cache
            if (time.monotonic() - ts) < ttl:
                return names
        names = await _probe_installed_scanners()
        _readiness_cache = (time.monotonic(), names)
        return names


# ---------------------------------------------------------------------------
# Operational HTTP endpoints (health / readiness / metrics)
# ---------------------------------------------------------------------------
# Only meaningful for HTTP transports; harmless under stdio (never hit).
try:
    from starlette.requests import Request
    from starlette.responses import JSONResponse, PlainTextResponse

    @mcp.custom_route("/health", methods=["GET"])
    async def _health(_request: "Request"):
        """Liveness probe — always 200 while the process is up."""
        return JSONResponse({"status": "ok", "version": __version__})

    @mcp.custom_route("/ready", methods=["GET"])
    async def _ready(_request: "Request"):
        """Readiness probe — reports which scanners are installed (cached)."""
        installed = await _installed_scanners()
        ready = bool(installed)
        return JSONResponse(
            {
                "status": "ready" if ready else "degraded",
                "scanners_installed": installed,
                "scanners_total": len(ScannerFactory.list_scanners()),
            },
            status_code=200 if ready else 503,
        )

    @mcp.custom_route("/metrics", methods=["GET"])
    async def _metrics(_request: "Request"):
        """Prometheus text exposition of in-process metrics."""
        return PlainTextResponse(
            metrics.render_prometheus(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

except Exception as _route_err:  # pragma: no cover - defensive
    logger.debug("Could not register operational routes: %s", _route_err)

# Valid enum values for input validation
_VALID_SEVERITIES = {s.value for s in SeverityLevel}
_VALID_CONFIDENCES = {c.value for c in ConfidenceLevel}
_VALID_OUTPUT_FORMATS = {"markdown", "json"}

# ---------------------------------------------------------------------------
# Authentication & audit
# ---------------------------------------------------------------------------
# Dedicated audit logger — one structured JSON line per tool invocation.
_audit_logger = logging.getLogger("sast_mcp_server.audit")

# Process-wide rate limiter (no-op unless SAST_MCP_RATE_LIMIT_PER_MIN > 0).
_rate_limiter = RateLimiter()


def _client_id() -> str:
    """Identify the caller for rate limiting (bearer token, then IP, then local)."""
    token = _current_token()
    if token:
        # Don't store the raw token; a short hash is enough to key a bucket.
        import hashlib

        return "tok:" + hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
    try:
        from fastmcp.server.dependencies import get_http_headers

        headers = get_http_headers() or {}
    except Exception:
        return "local"
    fwd = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For")
    if fwd:
        return "ip:" + fwd.split(",")[0].strip()
    return "local"


def _current_token() -> str | None:
    """Extract the bearer token from the active HTTP request, if any.

    Returns None for stdio/local transports (no request context), which the
    auth layer treats as "no token" — harmless when auth is disabled.
    """
    try:
        from fastmcp.server.dependencies import get_http_headers

        headers = get_http_headers() or {}
    except Exception:
        return None
    raw = headers.get("authorization") or headers.get("Authorization") or ""
    raw = raw.strip()
    if raw.lower().startswith("bearer "):
        return raw[7:].strip() or None
    return raw or None


def _emit_audit(
    tool: str, user: str | None, scope: str, target: str, status: str, **extra
) -> None:
    """Write a structured JSON audit record to stderr."""
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tool": tool,
        "user": user,
        "scope": scope,
        "target": target,
        "status": status,
        **extra,
    }
    _audit_logger.info(json.dumps(record))


def audited(required_scope: str) -> Callable:
    """Decorator: enforce ``required_scope`` and emit an audit record per call.

    Applied *under* ``@mcp.tool()`` so FastMCP still sees the wrapped function's
    signature (``functools.wraps`` preserves it). When auth is disabled (stdio),
    every call is authorized as the anonymous local user.
    """

    def decorator(func: Callable[..., Awaitable[str]]) -> Callable[..., Awaitable[str]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> str:
            tool = func.__name__
            target = str(
                kwargs.get("target_path")
                or kwargs.get("sarif_path")
                or kwargs.get("repo")
                or (args[0] if args else "")
            )

            # Rate limit before doing any work (HTTP transports only).
            if _rate_limiter.enabled and not _rate_limiter.check(_client_id()):
                _emit_audit(tool, None, required_scope, target, "rate_limited")
                metrics.inc(
                    "sast_tool_calls_total",
                    labels={"tool": tool, "status": "rate_limited"},
                )
                return (
                    "Error: rate limit exceeded. Too many requests; "
                    "retry in a moment."
                )

            provider = AuthProvider()
            try:
                ctx = authorize(provider, _current_token(), required_scope)
            except AuthError as err:
                _emit_audit(tool, None, required_scope, target, "denied", reason=str(err))
                metrics.inc("sast_tool_calls_total", labels={"tool": tool, "status": "denied"})
                return f"Error: authentication failed: {err}"

            start = time.time()
            result = await func(*args, **kwargs)
            duration_s = time.time() - start
            _emit_audit(
                tool, ctx.user_id, required_scope, target, "ok",
                duration_ms=int(duration_s * 1000),
            )
            metrics.inc("sast_tool_calls_total", labels={"tool": tool, "status": "ok"})
            metrics.observe("sast_tool_duration_seconds", duration_s, labels={"tool": tool})
            return result

        return wrapper

    return decorator


def _validate_output_format(fmt: str) -> str | None:
    """Return an error string if ``fmt`` is not a supported output format."""
    if fmt not in _VALID_OUTPUT_FORMATS:
        return (
            f"Error: Invalid output_format '{fmt}'. "
            f"Valid values: {', '.join(sorted(_VALID_OUTPUT_FORMATS))}."
        )
    return None


def _findings_as_json(findings, **meta) -> str:
    """Serialize findings (plus metadata) as a machine-readable JSON string."""
    payload = dict(meta)
    payload["findings"] = [f.to_dict() for f in findings]
    return json.dumps(payload, indent=2)


def _format_findings_md(findings) -> str:
    """Render a list of findings as the standard markdown finding blocks."""
    output: list[str] = []
    for f in findings:
        d = f.to_dict()
        output.append(f"#### [{d['severity']}] {d['title']}")
        output.append(f"**Scanner:** {d['scanner']}")
        output.append(f"**File:** {d['file']}:{d['line_start']}-{d['line_end']}")
        output.append(f"**Confidence:** {d['confidence']}")
        output.append(f"**Hash:** `{d['finding_hash']}`")
        if d.get("message"):
            output.append(f"**Details:** {d['message']}")
        output.append("\n**Context:**")
        output.append(
            "```"
            + d.get("language", "")
            + "\n"
            + d.get("context", "No context available.")
            + "\n```"
        )
        if d.get("data_flow"):
            output.append("\n**Data Flow:**")
            for step in d["data_flow"]:
                output.append(
                    f"- {step['file']}:{step['line']} - `{step['code_snippet']}`"
                )
        output.append("---\n")
    return "\n".join(output)


@mcp.tool()
@audited(SCOPE_SCAN_READ)
async def scan_vulnerabilities(
    target_path: str,
    scanner_name: str = "bearer",
    min_severity: str = "LOW",
    min_confidence: str = "LOW",
    git_diff_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    output_format: str = "markdown",
    use_cache: bool = False,
) -> str:
    """Scan a target directory for security vulnerabilities using a SAST tool.

    Args:
        target_path: The absolute path to the directory or file to scan.
        scanner_name: The scanner to use ('bandit', 'njsscan', 'bearer',
            'semgrep'). Defaults to 'bearer'.
        min_severity: Minimum severity to report (LOW, MEDIUM, HIGH, CRITICAL).
        min_confidence: Minimum confidence to report (LOW, MEDIUM, HIGH).
        git_diff_only: If true, only reports findings in files modified in git diff.
        limit: Maximum number of findings to return (for pagination).
        offset: Pagination offset.
        output_format: 'markdown' (human-readable, default) or 'json'
            (machine-readable list of findings for agents / CI).
        use_cache: If true, reuse the last cached scan when the target's files
            are unchanged (incremental scan). Ignored when git_diff_only is set.
    """
    # --- Input validation ---
    if not os.path.exists(target_path):
        return f"Error: Target path '{target_path}' does not exist."

    output_format = output_format.lower().strip()
    fmt_error = _validate_output_format(output_format)
    if fmt_error:
        return fmt_error

    min_severity = min_severity.upper().strip()
    min_confidence = min_confidence.upper().strip()

    if min_severity not in _VALID_SEVERITIES:
        return (
            f"Error: Invalid min_severity '{min_severity}'. "
            f"Valid values: {', '.join(sorted(_VALID_SEVERITIES))}"
        )
    if min_confidence not in _VALID_CONFIDENCES:
        return (
            f"Error: Invalid min_confidence '{min_confidence}'. "
            f"Valid values: {', '.join(sorted(_VALID_CONFIDENCES))}"
        )

    if limit < 1:
        return "Error: limit must be >= 1."
    if offset < 0:
        return "Error: offset must be >= 0."

    # --- Scanner setup ---
    try:
        scanner = ScannerFactory.get_scanner(scanner_name)
    except ValueError as e:
        return f"Error: {e}"

    try:
        await scanner.check_dependency()
    except RuntimeError as e:
        return f"Dependency Check Failed: {e}"

    # --- Git diff filter ---
    modified_files = None
    if git_diff_only:
        modified_files = await get_modified_files(target_path)
        if not modified_files:
            return "No modified files found in git diff to scan."

    # --- Incremental cache lookup (only for whole-target scans) ---
    fingerprint = ""
    cache = ScanCache(target_path)
    if use_cache and not git_diff_only:
        fingerprint = compute_target_fingerprint(target_path)
        fresh = cache.load_fresh(scanner_name, fingerprint)
        if fresh is not None:
            findings = fresh.findings
            ignore_manager = IgnoreManager(target_path)
            findings = [
                f for f in findings if not ignore_manager.is_ignored(f.finding_hash)
            ]
            total_findings = len(findings)
            paginated = findings[offset : offset + limit]
            if output_format == "json":
                return _findings_as_json(
                    paginated,
                    scanner=scanner_name,
                    total=total_findings,
                    offset=offset,
                    returned=len(paginated),
                    cached=True,
                )
            header = (
                f"### SAST Scan Results ({scanner_name}) — cached "
                f"(target unchanged)\n"
                f"Showing {len(paginated)} of {total_findings} findings "
                f"(Offset: {offset})\n"
            )
            return header + _format_findings_md(paginated)

    # --- Run scan ---
    try:
        findings = await scanner.scan(
            target_path,
            min_severity=min_severity,
            min_confidence=min_confidence,
            modified_files=modified_files,
            timeout=SCAN_TIMEOUT,
        )
    except RuntimeError as e:
        return f"Scan Failed: {e}"

    # --- Persist for incremental reuse ---
    if use_cache and not git_diff_only:
        cache.save_scan(scanner_name, findings, fingerprint=fingerprint)

    # --- Filter ignored findings ---
    ignore_manager = IgnoreManager(target_path)
    findings = [
        f for f in findings if not ignore_manager.is_ignored(f.finding_hash)
    ]

    total_findings = len(findings)
    paginated = findings[offset : offset + limit]

    if output_format == "json":
        return _findings_as_json(
            paginated,
            scanner=scanner_name,
            total=total_findings,
            offset=offset,
            returned=len(paginated),
        )

    if not paginated:
        return (
            f"Scan complete. 0 vulnerabilities found matching criteria "
            f"(Total before pagination: {total_findings})."
        )

    # --- Format output ---
    output = [f"### SAST Scan Results ({scanner_name})"]
    output.append(
        f"Showing {len(paginated)} of {total_findings} findings (Offset: {offset})\n"
    )

    for f in paginated:
        d = f.to_dict()
        output.append(f"#### [{d['severity']}] {d['title']}")
        output.append(f"**File:** {d['file']}:{d['line_start']}-{d['line_end']}")
        output.append(f"**Confidence:** {d['confidence']}")
        output.append(f"**Hash:** `{d['finding_hash']}`")
        if d.get("message"):
            output.append(f"**Details:** {d['message']}")

        output.append("\n**Context:**")
        output.append(
            "```"
            + d.get("language", "")
            + "\n"
            + d.get("context", "No context available.")
            + "\n```"
        )

        if d.get("data_flow"):
            output.append("\n**Data Flow:**")
            for step in d["data_flow"]:
                output.append(
                    f"- {step['file']}:{step['line']} - `{step['code_snippet']}`"
                )

        output.append("---\n")

    return "\n".join(output)


@mcp.tool()
@audited(SCOPE_CONFIG_WRITE)
async def ignore_vulnerability(
    target_path: str, finding_hash: str, reason: str = ""
) -> str:
    """Ignore a specific vulnerability finding so it won't appear in future scans.

    Args:
        target_path: The root directory of the project (where .sast-mcp-ignore.json lives).
        finding_hash: The unique hash of the finding to ignore (shown in scan results).
        reason: Optional justification for ignoring the vulnerability.
    """
    if not os.path.isdir(target_path):
        return f"Error: Target path '{target_path}' is not a valid directory."

    ignore_manager = IgnoreManager(target_path)
    ignore_manager.ignore(finding_hash, reason)
    return (
        f"Successfully ignored finding `{finding_hash}` in "
        f"`{target_path}/.sast-mcp-ignore.json`. "
        f"Reason: {reason or 'No reason provided.'}"
    )


@mcp.tool()
@audited(SCOPE_CONFIG_WRITE)
async def unignore_vulnerability(target_path: str, finding_hash: str) -> str:
    """Remove a vulnerability from the ignore list so it appears in future scans again.

    Args:
        target_path: The root directory of the project.
        finding_hash: The unique hash of the finding to unignore.
    """
    if not os.path.isdir(target_path):
        return f"Error: Target path '{target_path}' is not a valid directory."

    ignore_manager = IgnoreManager(target_path)
    if ignore_manager.unignore(finding_hash):
        return f"Successfully unignored finding `{finding_hash}`. It will appear in future scans."
    else:
        return f"Finding `{finding_hash}` was not in the ignore list."


@mcp.tool()
@audited(SCOPE_SCAN_READ)
async def list_scanners() -> str:
    """List all available SAST scanners, their status, and supported languages.

    Returns information about each scanner including whether it is installed
    and ready to use, what languages it supports, and how to install it.
    """
    output = ["### Available SAST Scanners\n"]

    for name in ScannerFactory.list_scanners():
        info = SCANNER_INFO.get(name, {})
        scanner = ScannerFactory.get_scanner(name)

        # Check if the scanner binary is available
        version = None
        try:
            await scanner.check_dependency()
            status = "✅ Installed"
            version = await scanner.get_version()
        except RuntimeError:
            status = "❌ Not installed"

        output.append(f"#### {name}")
        if version:
            output.append(f"- **Status:** {status} (v{version})")
        else:
            output.append(f"- **Status:** {status}")
        output.append(f"- **Languages:** {info.get('languages', 'Unknown')}")
        output.append(f"- **Description:** {info.get('description', '')}")
        output.append(f"- **Install:** `{info.get('install', 'See documentation')}`")
        output.append("")

    return "\n".join(output)


@mcp.tool()
@audited(SCOPE_SCAN_READ)
async def list_ignored_vulnerabilities(target_path: str) -> str:
    """List all currently ignored vulnerability findings for a project.

    Args:
        target_path: The root directory of the project.
    """
    if not os.path.isdir(target_path):
        return f"Error: Target path '{target_path}' is not a valid directory."

    ignore_manager = IgnoreManager(target_path)
    ignored = ignore_manager.list_ignored()

    if not ignored:
        return "No ignored vulnerabilities found for this project."

    output = [f"### Ignored Vulnerabilities ({len(ignored)} total)\n"]
    for entry in ignored:
        output.append(f"- **Hash:** `{entry['hash']}`")
        output.append(f"  - Reason: {entry.get('reason', 'No reason')}")
        output.append(f"  - Ignored at: {entry.get('ignored_at', 'Unknown')}")
        output.append("")

    return "\n".join(output)


@mcp.tool()
@audited(SCOPE_SCAN_READ)
async def scan_git_history(
    target_path: str = ".",
    min_severity: str = "LOW",
    output_format: str = "markdown",
) -> str:
    """Scan the entire git history for leaked secrets and credentials using Gitleaks.

    Traditional SAST only scans the current state of files. This tool deeply
    analyzes the `.git` directory to find API keys, passwords, and tokens
    that were committed in the past but may still be valid.

    Args:
        target_path: Path to the repository root (must contain a .git directory).
        min_severity: Minimum severity threshold (defaults to LOW).
        output_format: 'markdown' (human-readable, default) or 'json'
            (machine-readable list of findings for agents / CI).

    Returns:
        Formatted markdown summary of leaked secrets.
    """
    target_path = os.path.abspath(target_path)
    output_format = output_format.lower().strip()
    fmt_error = _validate_output_format(output_format)
    if fmt_error:
        return fmt_error
    if not os.path.isdir(os.path.join(target_path, ".git")):
        return f"Error: {target_path} is not a valid git repository. A .git directory is required."

    try:
        scanner = ScannerFactory.get_scanner("gitleaks")
        await scanner.check_dependency()
    except ValueError as e:
        return f"Error: {str(e)}"
    except RuntimeError as e:
        return f"Error: {str(e)}"

    try:
        findings = await scanner.scan(
            target_path=target_path,
            min_severity=min_severity,
        )
    except Exception as e:
        logger.error(f"Scan failed: {e}", exc_info=True)
        return f"Scan failed: {str(e)}"

    if output_format == "json":
        if findings:
            ScanCache(target_path).save_scan(scanner.name, findings)
        return _findings_as_json(findings, scanner="gitleaks", total=len(findings))

    if not findings:
        return "✅ No leaked secrets found in the git history."

    # Cache the scan
    cache = ScanCache(target_path)
    cache.save_scan(scanner.name, findings)

    summary = f"⚠️ Found {len(findings)} leaked secrets in git history:\n\n"
    for idx, f in enumerate(findings, 1):
        summary += f"{idx}. **{f.title}** ({f.severity.value})\n"
        summary += f"   - File: `{f.file}:{f.line_start}`\n"
        summary += f"   - {f.message}\n"
        summary += f"   - Context: `{f.context}`\n\n"

    summary += (
        "\n> **Action Required**: Use `git-filter-repo` or BFG Repo-Cleaner to "
        "completely remove these secrets from history, then rotate the exposed "
        "credentials immediately."
    )
    return summary


@mcp.tool()
@audited(SCOPE_SCAN_WRITE)
async def run_active_scan(
    target_path: str,
    docker_compose_file: str,
    target_url: str,
) -> str:
    """Run an active dynamic scan (DAST) using OWASP ZAP.

    Unlike SAST which only looks at code, this orchestrates spinning up the
    application via Docker Compose, waiting for it to be ready, and then
    running a ZAP dynamic baseline scan against the running instance.

    Args:
        target_path: Path to the directory containing the docker-compose file.
        docker_compose_file: The name of the docker-compose file (e.g. docker-compose.yml).
        target_url: The URL of the target application once it's up (e.g. http://localhost:8080).

    Returns:
        Formatted markdown summary of runtime vulnerabilities.
    """
    target_path = os.path.abspath(target_path)
    if not os.path.isdir(target_path):
        return f"Error: target_path {target_path} is not a valid directory."

    try:
        scanner = ScannerFactory.get_scanner("zap")
        await scanner.check_dependency()
    except Exception as e:
        return f"Error initializing ZAP: {str(e)}"

    # We must typecast to ZapScanner or just use it directly
    if not hasattr(scanner, "run_dynamic_scan"):
        return "Error: Scanner does not support dynamic scanning."

    try:
        # pylint: disable=no-member
        findings = await scanner.run_dynamic_scan(
            target_path=target_path,
            docker_compose_file=docker_compose_file,
            target_url=target_url
        )
    except Exception as e:
        logger.error(f"ZAP Dynamic Scan failed: {e}", exc_info=True)
        return f"Dynamic scan failed: {str(e)}"

    if not findings:
        return f"✅ ZAP Active Scan completed against {target_url}. No vulnerabilities found."

    summary = f"⚠️ Found {len(findings)} runtime vulnerabilities in {target_url}:\n\n"
    for idx, f in enumerate(findings, 1):
        summary += f"{idx}. **{f.title}** ({f.severity.value})\n"
        summary += f"   - {f.message}\n\n"
        summary += f"   ```\n   {f.context}\n   ```\n\n"

    return summary


@mcp.tool()
@audited(SCOPE_SCAN_READ)
async def export_sarif(
    target_path: str,
    scanner_name: str = "bearer",
    min_severity: str = "LOW",
    min_confidence: str = "LOW",
    output_path: str = "",
) -> str:
    """Run a SAST scan and export results in SARIF 2.1.0 format for CI/CD integration.

    SARIF is the industry standard format consumed by GitHub Code Scanning,
    GitLab SAST, Azure DevOps, and other CI/CD platforms.

    Args:
        target_path: The absolute path to the directory or file to scan.
        scanner_name: The scanner to use ('bandit', 'njsscan', 'bearer',
            'semgrep', 'trivy', 'codeql', 'checkov'). Defaults to 'bearer'.
        min_severity: Minimum severity to report (LOW, MEDIUM, HIGH, CRITICAL).
        min_confidence: Minimum confidence to report (LOW, MEDIUM, HIGH).
        output_path: Optional path to write the SARIF file. If empty, returns
            the SARIF JSON as a string.
    """
    # --- Input validation ---
    if not os.path.exists(target_path):
        return f"Error: Target path '{target_path}' does not exist."

    min_severity = min_severity.upper().strip()
    min_confidence = min_confidence.upper().strip()

    if min_severity not in _VALID_SEVERITIES:
        return (
            f"Error: Invalid min_severity '{min_severity}'. "
            f"Valid values: {', '.join(sorted(_VALID_SEVERITIES))}"
        )
    if min_confidence not in _VALID_CONFIDENCES:
        return (
            f"Error: Invalid min_confidence '{min_confidence}'. "
            f"Valid values: {', '.join(sorted(_VALID_CONFIDENCES))}"
        )

    # --- Scanner setup ---
    try:
        scanner = ScannerFactory.get_scanner(scanner_name)
    except ValueError as e:
        return f"Error: {e}"

    try:
        await scanner.check_dependency()
    except RuntimeError as e:
        return f"Dependency Check Failed: {e}"

    # --- Run scan ---
    try:
        findings = await scanner.scan(
            target_path,
            min_severity=min_severity,
            min_confidence=min_confidence,
            timeout=SCAN_TIMEOUT,
        )
    except RuntimeError as e:
        return f"Scan Failed: {e}"

    # --- Filter ignored findings ---
    ignore_manager = IgnoreManager(target_path)
    findings = [
        f for f in findings if not ignore_manager.is_ignored(f.finding_hash)
    ]

    # --- Convert to SARIF ---
    sarif_doc = findings_to_sarif(findings, scanner_name, __version__)
    sarif_json = json.dumps(sarif_doc, indent=2)

    if output_path:
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(sarif_json)
            return (
                f"SARIF export complete. {len(findings)} findings exported to "
                f"`{output_path}` in SARIF 2.1.0 format. "
                f"Upload this file to GitHub Code Scanning, GitLab SAST, "
                f"or any SARIF-compatible platform."
            )
        except OSError as e:
            return f"Error writing SARIF file: {e}"

    # Return SARIF as string if no output_path
    return (
        f"### SARIF Export ({scanner_name})\n"
        f"{len(findings)} findings in SARIF 2.1.0 format:\n\n"
        f"```json\n{sarif_json}\n```"
    )


@mcp.tool()
@audited(SCOPE_SCAN_READ)
async def scan_all(
    target_path: str,
    min_severity: str = "MEDIUM",
    min_confidence: str = "LOW",
    git_diff_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    output_format: str = "markdown",
    use_cache: bool = False,
) -> str:
    """Scan with ALL installed scanners in parallel, returning deduplicated results.

    Automatically detects which scanners are installed, runs them concurrently,
    and deduplicates findings across scanners using content-based hashing.
    This is the recommended tool for comprehensive security scanning.

    Args:
        target_path: The absolute path to the directory or file to scan.
        min_severity: Minimum severity to report (LOW, MEDIUM, HIGH, CRITICAL).
            Defaults to MEDIUM to reduce noise from multiple scanners.
        min_confidence: Minimum confidence to report (LOW, MEDIUM, HIGH).
        git_diff_only: If true, only reports findings in files modified in git diff.
        limit: Maximum number of findings to return (for pagination).
        offset: Pagination offset.
        output_format: 'markdown' (human-readable, default) or 'json'
            (machine-readable list of findings for agents / CI).
        use_cache: If true, reuse the last cached scan_all when the target's
            files are unchanged (incremental scan). Ignored with git_diff_only.
    """
    # --- Input validation ---
    if not os.path.exists(target_path):
        return f"Error: Target path '{target_path}' does not exist."

    output_format = output_format.lower().strip()
    fmt_error = _validate_output_format(output_format)
    if fmt_error:
        return fmt_error

    min_severity = min_severity.upper().strip()
    min_confidence = min_confidence.upper().strip()

    if min_severity not in _VALID_SEVERITIES:
        return (
            f"Error: Invalid min_severity '{min_severity}'. "
            f"Valid values: {', '.join(sorted(_VALID_SEVERITIES))}"
        )
    if min_confidence not in _VALID_CONFIDENCES:
        return (
            f"Error: Invalid min_confidence '{min_confidence}'. "
            f"Valid values: {', '.join(sorted(_VALID_CONFIDENCES))}"
        )

    if limit < 1:
        return "Error: limit must be >= 1."
    if offset < 0:
        return "Error: offset must be >= 0."

    # --- Git diff filter ---
    modified_files = None
    if git_diff_only:
        modified_files = await get_modified_files(target_path)
        if not modified_files:
            return "No modified files found in git diff to scan."

    # --- Incremental cache lookup ---
    fingerprint = ""
    cache = ScanCache(target_path)
    used_scanners: list[str]
    skipped_scanners: list[str]
    if use_cache and not git_diff_only:
        fingerprint = compute_target_fingerprint(target_path)
        fresh = cache.load_fresh("scan_all", fingerprint)
        if fresh is not None:
            ignore_manager = IgnoreManager(target_path)
            findings = [
                f for f in fresh.findings
                if not ignore_manager.is_ignored(f.finding_hash)
            ]
            total_findings = len(findings)
            paginated = findings[offset : offset + limit]
            if output_format == "json":
                return _findings_as_json(
                    paginated,
                    total=total_findings,
                    offset=offset,
                    returned=len(paginated),
                    cached=True,
                )
            header = (
                "### Multi-Scanner SAST Results — cached (target unchanged)\n"
                f"Showing {len(paginated)} of {total_findings} deduplicated "
                f"findings (Offset: {offset})\n"
            )
            return header + _format_findings_md(paginated)

    # --- Run all scanners ---
    findings, used_scanners, skipped_scanners = await run_all_scanners(
        target_path,
        min_severity=min_severity,
        min_confidence=min_confidence,
        modified_files=modified_files,
        timeout=SCAN_TIMEOUT,
    )

    if not used_scanners:
        return (
            "No scanners are installed. Install at least one scanner:\n"
            + "\n".join(
                f"- **{name}**: `{info.get('install', 'See docs')}`"
                for name, info in SCANNER_INFO.items()
            )
        )

    # --- Persist for incremental reuse ---
    if use_cache and not git_diff_only:
        cache.save_scan("scan_all", findings, fingerprint=fingerprint)

    # --- Filter ignored findings ---
    ignore_manager = IgnoreManager(target_path)
    findings = [
        f for f in findings if not ignore_manager.is_ignored(f.finding_hash)
    ]

    total_findings = len(findings)
    paginated = findings[offset : offset + limit]

    if output_format == "json":
        return _findings_as_json(
            paginated,
            scanners_used=sorted(used_scanners),
            scanners_skipped=sorted(skipped_scanners),
            total=total_findings,
            offset=offset,
            returned=len(paginated),
        )

    # --- Format output ---
    output = ["### Multi-Scanner SAST Results"]
    output.append(f"**Scanners used:** {', '.join(sorted(used_scanners))}")
    if skipped_scanners:
        skipped_str = ", ".join(sorted(skipped_scanners))
        output.append(
            f"**Scanners skipped (not installed):** {skipped_str}"
        )
    output.append(
        f"Showing {len(paginated)} of {total_findings} deduplicated findings "
        f"(Offset: {offset})\n"
    )

    if not paginated:
        output.append("No vulnerabilities found matching criteria.")
        return "\n".join(output)

    for f in paginated:
        d = f.to_dict()
        output.append(f"#### [{d['severity']}] {d['title']}")
        output.append(f"**Scanner:** {d['scanner']}")
        output.append(f"**File:** {d['file']}:{d['line_start']}-{d['line_end']}")
        output.append(f"**Confidence:** {d['confidence']}")
        output.append(f"**Hash:** `{d['finding_hash']}`")
        if d.get("message"):
            output.append(f"**Details:** {d['message']}")

        output.append("\n**Context:**")
        output.append(
            "```"
            + d.get("language", "")
            + "\n"
            + d.get("context", "No context available.")
            + "\n```"
        )

        if d.get("data_flow"):
            output.append("\n**Data Flow:**")
            for step in d["data_flow"]:
                output.append(
                    f"- {step['file']}:{step['line']} - `{step['code_snippet']}`"
                )

        output.append("---\n")

    return "\n".join(output)


# ---------------------------------------------------------------------------
# Container image scanning
# ---------------------------------------------------------------------------
@mcp.tool()
@audited(SCOPE_SCAN_READ)
async def scan_image(
    image_ref: str,
    scanner_name: str = "trivy",
    min_severity: str = "MEDIUM",
    output_format: str = "markdown",
) -> str:
    """Scan a container image for vulnerabilities and secrets.

    Pulls and analyzes a container image reference (e.g. `nginx:1.25`,
    `ghcr.io/org/app@sha256:...`) with Trivy or Grype, returning the same
    normalized findings as a source scan.

    Args:
        image_ref: The image reference to scan.
        scanner_name: 'trivy' (default) or 'grype'.
        min_severity: Minimum severity to report (LOW, MEDIUM, HIGH, CRITICAL).
        output_format: 'markdown' (default) or 'json'.
    """
    output_format = output_format.lower().strip()
    fmt_error = _validate_output_format(output_format)
    if fmt_error:
        return fmt_error

    min_severity = min_severity.upper().strip()
    if min_severity not in _VALID_SEVERITIES:
        return (
            f"Error: Invalid min_severity '{min_severity}'. "
            f"Valid values: {', '.join(sorted(_VALID_SEVERITIES))}"
        )

    scanner_name = scanner_name.lower().strip()
    if scanner_name not in {"trivy", "grype"}:
        return "Error: scanner_name must be 'trivy' or 'grype' for image scans."

    try:
        scanner = ScannerFactory.get_scanner(scanner_name)
        await scanner.check_dependency()
    except (ValueError, RuntimeError) as e:
        return f"Error: {e}"

    if not hasattr(scanner, "scan_image"):
        return f"Error: scanner '{scanner_name}' does not support image scanning."

    try:
        findings = await scanner.scan_image(  # type: ignore[attr-defined]
            image_ref, min_severity=min_severity, timeout=SCAN_TIMEOUT
        )
    except RuntimeError as e:
        return f"Image scan failed: {e}"

    if output_format == "json":
        return _findings_as_json(
            findings, scanner=scanner_name, image=image_ref, total=len(findings)
        )

    if not findings:
        return f"✅ No vulnerabilities found in image `{image_ref}` (scanner: {scanner_name})."

    output = [
        f"### Image Scan Results — `{image_ref}` ({scanner_name})",
        f"{len(findings)} finding(s)\n",
    ]
    return "\n".join(output) + _format_findings_md(findings)


# ---------------------------------------------------------------------------
# Baseline Tools
# ---------------------------------------------------------------------------
@mcp.tool()
@audited(SCOPE_SCAN_WRITE)
async def save_baseline(
    target_path: str,
    tag: str = "latest",
    scanner_name: str = "bearer",
    min_severity: str = "LOW",
    min_confidence: str = "LOW",
) -> str:
    """Run a scan and save the results as a named baseline for future comparison.

    Args:
        target_path: The absolute path to the directory to scan.
        scanner_name: Scanner to use, or 'scan_all' to baseline the
            deduplicated results of every installed scanner (recommended for
            policy gating with `evaluate_policy(fail_on_new=True)`).
            Defaults to 'bearer'.
        tag: A name for this baseline (e.g., 'main', 'pre-release').
            Defaults to 'latest'.
        min_severity: Minimum severity to include (LOW, MEDIUM, HIGH, CRITICAL).
        min_confidence: Minimum confidence to include (LOW, MEDIUM, HIGH).
    """
    if not os.path.exists(target_path):
        return f"Error: Target path '{target_path}' does not exist."

    min_severity = min_severity.upper().strip()
    min_confidence = min_confidence.upper().strip()

    if min_severity not in _VALID_SEVERITIES:
        return (
            f"Error: Invalid min_severity '{min_severity}'. "
            f"Valid values: {', '.join(sorted(_VALID_SEVERITIES))}"
        )
    if min_confidence not in _VALID_CONFIDENCES:
        return (
            f"Error: Invalid min_confidence '{min_confidence}'. "
            f"Valid values: {', '.join(sorted(_VALID_CONFIDENCES))}"
        )

    scanner_name = scanner_name.strip()
    start_ms = int(time.time() * 1000)

    if scanner_name == "scan_all":
        # Aggregate baseline across all installed scanners.
        findings, used_scanners, _ = await run_all_scanners(
            target_path,
            min_severity=min_severity,
            min_confidence=min_confidence,
            timeout=SCAN_TIMEOUT,
        )
        if not used_scanners:
            return "No scanners are installed; cannot save a baseline."
    else:
        try:
            scanner = ScannerFactory.get_scanner(scanner_name)
        except ValueError as e:
            return f"Error: {e}"

        try:
            await scanner.check_dependency()
        except RuntimeError as e:
            return f"Dependency Check Failed: {e}"

        try:
            findings = await scanner.scan(
                target_path,
                min_severity=min_severity,
                min_confidence=min_confidence,
                timeout=SCAN_TIMEOUT,
            )
        except RuntimeError as e:
            return f"Scan Failed: {e}"
    duration_ms = int(time.time() * 1000) - start_ms

    # Save to cache
    cache = ScanCache(target_path)
    cache_id = cache.save_scan(
        scanner_name=scanner_name,
        findings=findings,
        tag=tag,
        min_severity=min_severity,
        duration_ms=duration_ms,
    )

    return (
        f"✅ Baseline saved successfully!\n\n"
        f"**Tag:** `{tag}`\n"
        f"**Scanner:** {scanner_name}\n"
        f"**Findings:** {len(findings)}\n"
        f"**Duration:** {duration_ms}ms\n"
        f"**Cache ID:** `{cache_id}`\n\n"
        f"Use `compare_baseline` with `tag=\"{tag}\"` to compare "
        f"future scans against this baseline."
    )


@mcp.tool()
@audited(SCOPE_SCAN_READ)
async def compare_baseline(
    target_path: str,
    tag: str = "latest",
    scanner_name: str = "bearer",
    min_severity: str = "LOW",
    min_confidence: str = "LOW",
) -> str:
    """Compare current scan results against a saved baseline.

    Shows new vulnerabilities, fixed vulnerabilities, and severity trends.

    Args:
        target_path: The absolute path to the directory to scan.
        tag: The baseline tag to compare against. Defaults to 'latest'.
        scanner_name: Scanner to use. Defaults to 'bearer'.
        min_severity: Minimum severity (LOW, MEDIUM, HIGH, CRITICAL).
        min_confidence: Minimum confidence (LOW, MEDIUM, HIGH).
    """
    if not os.path.exists(target_path):
        return f"Error: Target path '{target_path}' does not exist."

    min_severity = min_severity.upper().strip()
    min_confidence = min_confidence.upper().strip()
    scanner_name = scanner_name.strip()

    if min_severity not in _VALID_SEVERITIES:
        return (
            f"Error: Invalid min_severity '{min_severity}'. "
            f"Valid values: {', '.join(sorted(_VALID_SEVERITIES))}"
        )

    # Load baseline
    cache = ScanCache(target_path)
    baseline = cache.load_by_tag(scanner_name, tag)
    if baseline is None:
        return (
            f"No baseline found with tag '{tag}' for scanner '{scanner_name}'.\n\n"
            f"Create one first with:\n"
            f"`save_baseline(target_path=\"{target_path}\", "
            f"tag=\"{tag}\", scanner_name=\"{scanner_name}\")`"
        )

    # Run current scan. 'scan_all' diffs against an aggregated baseline (the
    # form save_baseline / evaluate_policy(fail_on_new=True) use); any other
    # value runs that single scanner.
    if scanner_name == "scan_all":
        current_findings, used_scanners, _ = await run_all_scanners(
            target_path,
            min_severity=min_severity,
            min_confidence=min_confidence,
            timeout=SCAN_TIMEOUT,
        )
        if not used_scanners:
            return "No scanners are installed; cannot compare against the baseline."
    else:
        try:
            scanner = ScannerFactory.get_scanner(scanner_name)
        except ValueError as e:
            return f"Error: {e}"

        try:
            await scanner.check_dependency()
        except RuntimeError as e:
            return f"Dependency Check Failed: {e}"

        try:
            current_findings = await scanner.scan(
                target_path,
                min_severity=min_severity,
                min_confidence=min_confidence,
                timeout=SCAN_TIMEOUT,
            )
        except RuntimeError as e:
            return f"Scan Failed: {e}"

    # Compare
    diff = cache.compare(baseline, current_findings)

    # Format output
    output = ["### Baseline Comparison Report"]
    output.append(f"**Baseline tag:** `{tag}` (from {baseline.timestamp})")
    output.append(f"**Scanner:** {scanner_name}")
    output.append(
        f"**Baseline:** {diff.baseline_total} findings → "
        f"**Current:** {diff.current_total} findings\n"
    )

    # Severity trend
    output.append("#### Severity Trend")
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        trend = diff.severity_trend.get(sev, {})
        delta = trend.get("delta", 0)
        indicator = "🟢" if delta < 0 else ("🔴" if delta > 0 else "⚪")
        delta_str = f"+{delta}" if delta > 0 else str(delta)
        output.append(
            f"- {indicator} **{sev}:** {trend.get('baseline', 0)} → "
            f"{trend.get('current', 0)} ({delta_str})"
        )
    output.append("")

    # New findings
    if diff.new_findings:
        output.append(
            f"#### 🔴 New Findings ({len(diff.new_findings)})"
        )
        for f in diff.new_findings[:10]:
            output.append(
                f"- [{f.severity.value}] **{f.title}** — "
                f"{f.file}:{f.line_start}"
            )
        if len(diff.new_findings) > 10:
            output.append(
                f"  _(... and {len(diff.new_findings) - 10} more)_"
            )
        output.append("")

    # Fixed findings
    if diff.fixed_findings:
        output.append(
            f"#### 🟢 Fixed Findings ({len(diff.fixed_findings)})"
        )
        for f in diff.fixed_findings[:10]:
            output.append(
                f"- ~~[{f.severity.value}] {f.title} — "
                f"{f.file}:{f.line_start}~~"
            )
        if len(diff.fixed_findings) > 10:
            output.append(
                f"  _(... and {len(diff.fixed_findings) - 10} more)_"
            )
        output.append("")

    # Summary
    if not diff.new_findings and not diff.fixed_findings:
        output.append("#### ⚪ No changes since baseline.\n")
    elif not diff.new_findings:
        output.append("#### ✅ No new vulnerabilities! Security is improving.\n")

    output.append(
        f"**Unchanged:** {len(diff.unchanged_findings)} findings"
    )

    return "\n".join(output)


# ---------------------------------------------------------------------------
# Policy / CI gate
# ---------------------------------------------------------------------------
@mcp.tool()
@audited(SCOPE_SCAN_READ)
async def evaluate_policy(
    target_path: str,
    max_critical: int = 0,
    max_high: int = -1,
    max_medium: int = -1,
    fail_on_new: bool = False,
    baseline_tag: str = "latest",
    min_severity: str = "LOW",
    min_confidence: str = "LOW",
    output_format: str = "markdown",
) -> str:
    """Run all scanners and evaluate findings against a CI security policy.

    Returns an explicit PASS/FAIL verdict suitable for gating a pipeline. A
    threshold of ``-1`` means "no limit" for that severity. When ``fail_on_new``
    is set, the result also fails if any finding is new relative to the named
    baseline (created with ``save_baseline``).

    Args:
        target_path: The absolute path to the directory to scan.
        max_critical: Max allowed CRITICAL findings (default 0). -1 = unlimited.
        max_high: Max allowed HIGH findings. -1 = unlimited (default).
        max_medium: Max allowed MEDIUM findings. -1 = unlimited (default).
        fail_on_new: If true, fail when findings are new vs. the baseline.
        baseline_tag: Baseline tag to diff against when ``fail_on_new`` is set.
        min_severity: Minimum severity to include in the scan.
        min_confidence: Minimum confidence to include in the scan.
        output_format: 'markdown' (default) or 'json' (machine-readable verdict).
    """
    if not os.path.exists(target_path):
        return f"Error: Target path '{target_path}' does not exist."

    output_format = output_format.lower().strip()
    fmt_error = _validate_output_format(output_format)
    if fmt_error:
        return fmt_error

    min_severity = min_severity.upper().strip()
    min_confidence = min_confidence.upper().strip()
    if min_severity not in _VALID_SEVERITIES:
        return (
            f"Error: Invalid min_severity '{min_severity}'. "
            f"Valid values: {', '.join(sorted(_VALID_SEVERITIES))}"
        )

    findings, used_scanners, skipped_scanners = await run_all_scanners(
        target_path,
        min_severity=min_severity,
        min_confidence=min_confidence,
        timeout=SCAN_TIMEOUT,
    )

    if not used_scanners:
        return (
            "No scanners are installed; cannot evaluate policy. "
            "Install at least one scanner first."
        )

    # Filter ignored findings so suppressed FPs don't fail the gate.
    ignore_manager = IgnoreManager(target_path)
    findings = [f for f in findings if not ignore_manager.is_ignored(f.finding_hash)]

    # Count by severity.
    counts = {level.value: 0 for level in SeverityLevel}
    for f in findings:
        counts[f.severity.value] += 1

    # Evaluate thresholds (-1 means unlimited).
    violations: list[str] = []
    thresholds = {
        "CRITICAL": max_critical,
        "HIGH": max_high,
        "MEDIUM": max_medium,
    }
    for sev, limit_val in thresholds.items():
        if limit_val >= 0 and counts[sev] > limit_val:
            violations.append(
                f"{counts[sev]} {sev} finding(s) exceed the allowed maximum of {limit_val}"
            )

    # Optional baseline comparison.
    new_count = 0
    baseline_checked = False
    if fail_on_new:
        cache = ScanCache(target_path)
        baseline = cache.load_by_tag("scan_all", baseline_tag)
        if baseline is not None:
            baseline_checked = True
            diff = cache.compare(baseline, findings)
            new_count = len(diff.new_findings)
            if new_count > 0:
                violations.append(
                    f"{new_count} new finding(s) introduced vs. baseline '{baseline_tag}'"
                )

    passed = not violations

    if output_format == "json":
        return json.dumps(
            {
                "verdict": "PASS" if passed else "FAIL",
                "passed": passed,
                "counts": counts,
                "thresholds": thresholds,
                "violations": violations,
                "fail_on_new": fail_on_new,
                "baseline_checked": baseline_checked,
                "new_findings": new_count,
                "scanners_used": sorted(used_scanners),
                "scanners_skipped": sorted(skipped_scanners),
                "total_findings": len(findings),
            },
            indent=2,
        )

    verdict = "✅ PASS" if passed else "❌ FAIL"
    output = [f"### Security Policy: {verdict}"]
    output.append(f"**Scanners used:** {', '.join(sorted(used_scanners))}")
    output.append(
        "**Findings:** "
        + ", ".join(f"{sev}={counts[sev]}" for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"])
    )
    if fail_on_new:
        if baseline_checked:
            output.append(f"**New vs. baseline `{baseline_tag}`:** {new_count}")
        else:
            output.append(
                f"**New vs. baseline `{baseline_tag}`:** baseline not found (skipped)"
            )
    output.append("")
    if violations:
        output.append("#### Policy Violations")
        for v in violations:
            output.append(f"- ❌ {v}")
    else:
        output.append("All policy thresholds satisfied.")
    return "\n".join(output)


# ---------------------------------------------------------------------------
# Reporting (SBOM / HTML)
# ---------------------------------------------------------------------------
@mcp.tool()
@audited(SCOPE_SCAN_READ)
async def export_sbom(
    target_path: str,
    output_path: str = "",
    min_severity: str = "LOW",
    sca_only: bool = True,
    format: str = "cyclonedx",
) -> str:
    """Run all scanners and export an SBOM / vulnerability report.

    Produces the supply-chain artifact enterprises expect. In CycloneDX mode, if
    Syft is installed the component inventory is the *full* dependency list
    (not just vulnerable packages); otherwise components are derived from
    findings. SPDX mode emits an SPDX 2.3 document.

    Args:
        target_path: The absolute path to scan.
        output_path: File path to write the SBOM (empty = return inline).
        min_severity: Minimum severity to include.
        sca_only: Include only dependency (SCA) findings (default). Set False to
            include every finding as a vulnerability entry.
        format: 'cyclonedx' (default) or 'spdx'.
    """
    if not os.path.exists(target_path):
        return f"Error: Target path '{target_path}' does not exist."

    fmt = format.lower().strip()
    if fmt not in {"cyclonedx", "spdx"}:
        return "Error: format must be 'cyclonedx' or 'spdx'."

    min_severity = min_severity.upper().strip()
    if min_severity not in _VALID_SEVERITIES:
        return (
            f"Error: Invalid min_severity '{min_severity}'. "
            f"Valid values: {', '.join(sorted(_VALID_SEVERITIES))}"
        )

    findings, used_scanners, _ = await run_all_scanners(
        target_path, min_severity=min_severity, timeout=SCAN_TIMEOUT
    )
    if not used_scanners:
        return "No scanners are installed; cannot generate an SBOM."

    if fmt == "spdx":
        doc = findings_to_spdx(
            findings,
            project=os.path.basename(os.path.abspath(target_path)),
            version=__version__,
            sca_only=sca_only,
        )
        label = "SPDX 2.3 SBOM"
        summary = f"{len(doc['packages'])} packages"
    else:
        extra = await syft_cyclonedx_components(target_path)
        doc = findings_to_cyclonedx(
            findings, version=__version__, sca_only=sca_only, extra_components=extra
        )
        inventory = " (Syft inventory)" if extra else ""
        label = f"CycloneDX SBOM{inventory}"
        summary = (
            f"{len(doc['vulnerabilities'])} vulnerabilities, "
            f"{len(doc['components'])} components"
        )

    doc_json = json.dumps(doc, indent=2)

    if output_path:
        try:
            with open(output_path, "w", encoding="utf-8") as fh:
                fh.write(doc_json)
        except OSError as e:
            return f"Error writing SBOM file: {e}"
        return f"✅ {label} written to `{output_path}` ({summary})."

    return f"### {label}\n\n```json\n{doc_json}\n```"


@mcp.tool()
@audited(SCOPE_SCAN_READ)
async def generate_report(
    target_path: str,
    output_path: str = "",
    min_severity: str = "LOW",
    format: str = "html",
) -> str:
    """Run all scanners and render an executive security report (HTML or PDF).

    Args:
        target_path: The absolute path to scan.
        output_path: File path to write the report (empty = return inline HTML;
            required for PDF since it is binary).
        min_severity: Minimum severity to include.
        format: 'html' (default) or 'pdf'. PDF requires the optional [pdf] extra
            (`pip install "sast-mcp-server[pdf]"`).
    """
    if not os.path.exists(target_path):
        return f"Error: Target path '{target_path}' does not exist."

    fmt = format.lower().strip()
    if fmt not in {"html", "pdf"}:
        return "Error: format must be 'html' or 'pdf'."

    min_severity = min_severity.upper().strip()
    if min_severity not in _VALID_SEVERITIES:
        return (
            f"Error: Invalid min_severity '{min_severity}'. "
            f"Valid values: {', '.join(sorted(_VALID_SEVERITIES))}"
        )

    findings, used_scanners, _ = await run_all_scanners(
        target_path, min_severity=min_severity, timeout=SCAN_TIMEOUT
    )
    if not used_scanners:
        return "No scanners are installed; cannot generate a report."

    project = os.path.basename(os.path.abspath(target_path))

    if fmt == "pdf":
        if not pdf_available():
            return (
                "Error: PDF reports require the optional 'reportlab' dependency. "
                'Install it with: pip install "sast-mcp-server[pdf]"'
            )
        if not output_path:
            return "Error: output_path is required for PDF reports (binary output)."
        try:
            pdf_bytes = findings_to_pdf(
                findings, project=project, scanners=sorted(used_scanners)
            )
            with open(output_path, "wb") as fh:
                fh.write(pdf_bytes)
        except (PdfUnavailableError, OSError) as e:
            return f"Error writing PDF report: {e}"
        return (
            f"✅ PDF report written to `{output_path}` "
            f"({len(findings)} findings from {len(used_scanners)} scanners)."
        )

    report = findings_to_html(
        findings, project=project, scanners=sorted(used_scanners),
    )

    if output_path:
        try:
            with open(output_path, "w", encoding="utf-8") as fh:
                fh.write(report)
        except OSError as e:
            return f"Error writing report file: {e}"
        return (
            f"✅ HTML report written to `{output_path}` "
            f"({len(findings)} findings from {len(used_scanners)} scanners)."
        )

    return report


@mcp.tool()
@audited(SCOPE_SCAN_READ)
async def compliance_report(
    target_path: str,
    framework: str = "owasp",
    output_path: str = "",
    min_severity: str = "LOW",
) -> str:
    """Map findings to a compliance framework and report the posture.

    Buckets all findings against OWASP Top 10, SANS CWE Top 25, PCI DSS, or CIS
    using each finding's CWE / OWASP metadata.

    Args:
        target_path: The absolute path to scan.
        framework: 'owasp' (default), 'sans', 'pci', or 'cis'.
        output_path: Optional path to write the markdown report.
        min_severity: Minimum severity to include.
    """
    if not os.path.exists(target_path):
        return f"Error: Target path '{target_path}' does not exist."

    framework = framework.lower().strip()
    if framework not in {"owasp", "sans", "pci", "cis"}:
        return "Error: framework must be one of: owasp, sans, pci, cis."

    min_severity = min_severity.upper().strip()
    if min_severity not in _VALID_SEVERITIES:
        return (
            f"Error: Invalid min_severity '{min_severity}'. "
            f"Valid values: {', '.join(sorted(_VALID_SEVERITIES))}"
        )

    findings, used_scanners, _ = await run_all_scanners(
        target_path, min_severity=min_severity, timeout=SCAN_TIMEOUT
    )
    if not used_scanners:
        return "No scanners are installed; cannot generate a compliance report."

    project = os.path.basename(os.path.abspath(target_path))
    report = findings_to_compliance(findings, framework)
    markdown = compliance_to_markdown(report, project=project)

    if output_path:
        try:
            with open(output_path, "w", encoding="utf-8") as fh:
                fh.write(markdown)
        except OSError as e:
            return f"Error writing compliance report: {e}"
        return f"✅ {framework.upper()} compliance report written to `{output_path}`."

    return markdown


# ---------------------------------------------------------------------------
# Dashboard Integrations
# ---------------------------------------------------------------------------
@mcp.tool()
@audited(SCOPE_SCAN_WRITE)
async def upload_to_defectdojo(
    sarif_path: str,
    engagement_id: int,
    active: bool = True,
    verified: bool = False,
) -> str:
    """Upload a SARIF report to a DefectDojo engagement.

    Requires the DEFECTDOJO_URL and DEFECTDOJO_API_KEY environment variables.
    Generate the SARIF file first with `export_sarif(output_path=...)`.

    Args:
        sarif_path: Path to a SARIF file produced by `export_sarif`.
        engagement_id: Numeric ID of the target DefectDojo engagement.
        active: Mark imported findings as active.
        verified: Mark imported findings as verified.
    """
    if not os.path.isfile(sarif_path):
        return f"Error: SARIF file '{sarif_path}' does not exist."

    try:
        result = await _dd_upload(
            sarif_path,
            engagement_id,
            active=active,
            verified=verified,
        )
    except IntegrationError as e:
        return f"DefectDojo upload failed: {e}"

    test_id = result.get("test") or result.get("test_id")
    return (
        f"✅ Uploaded `{os.path.basename(sarif_path)}` to DefectDojo "
        f"engagement {engagement_id}."
        + (f" Test ID: {test_id}." if test_id else "")
    )


@mcp.tool()
@audited(SCOPE_SCAN_WRITE)
async def upload_to_github(
    sarif_path: str,
    repo: str,
    commit_sha: str,
    ref: str,
) -> str:
    """Upload a SARIF report to GitHub Code Scanning.

    Requires a GITHUB_TOKEN environment variable with `security_events: write`
    scope. Generate the SARIF file first with `export_sarif(output_path=...)`.

    Args:
        sarif_path: Path to a SARIF file produced by `export_sarif`.
        repo: Repository in `owner/name` form.
        commit_sha: Full SHA of the commit the results apply to.
        ref: Fully qualified ref, e.g. `refs/heads/main`.
    """
    if not os.path.isfile(sarif_path):
        return f"Error: SARIF file '{sarif_path}' does not exist."

    try:
        result = await _gh_upload(sarif_path, repo, commit_sha, ref)
    except IntegrationError as e:
        return f"GitHub upload failed: {e}"

    url = result.get("url", "")
    return (
        f"✅ Uploaded `{os.path.basename(sarif_path)}` to GitHub Code Scanning "
        f"for `{repo}` @ {commit_sha[:8]}."
        + (f"\nProcessing status: {url}" if url else "")
    )


# ---------------------------------------------------------------------------
# PR/MR comments, notifications, ticketing
# ---------------------------------------------------------------------------
@mcp.tool()
@audited(SCOPE_SCAN_WRITE)
async def comment_on_pr(
    provider: str,
    repo: str,
    pr_number: int,
    body: str,
) -> str:
    """Post a security summary comment on a GitHub PR or GitLab merge request.

    Credentials come from environment variables only: GITHUB_TOKEN for GitHub,
    or GITLAB_TOKEN (+ optional GITLAB_URL) for GitLab.

    Args:
        provider: 'github' or 'gitlab'.
        repo: For GitHub, 'owner/name'. For GitLab, the numeric project ID or
            URL-encoded 'group/project' path.
        pr_number: PR number (GitHub) or merge request IID (GitLab).
        body: Markdown comment body (e.g. a scan summary or gate result).
    """
    provider = provider.lower().strip()
    try:
        if provider == "github":
            result = await _gh_comment(repo, pr_number, body)
        elif provider == "gitlab":
            result = await _gl_comment(repo, pr_number, body)
        else:
            return "Error: provider must be 'github' or 'gitlab'."
    except IntegrationError as e:
        return f"Comment failed: {e}"

    link = result.get("html_url") or result.get("web_url") or ""
    return f"✅ Comment posted on {provider} {repo} #{pr_number}." + (
        f"\n{link}" if link else ""
    )


@mcp.tool()
@audited(SCOPE_SCAN_WRITE)
async def notify_slack(message: str) -> str:
    """Send a notification to the configured Slack incoming webhook.

    Requires the SLACK_WEBHOOK_URL environment variable.

    Args:
        message: The message text (Slack mrkdwn supported).
    """
    try:
        await _slack_notify(message)
    except IntegrationError as e:
        return f"Slack notification failed: {e}"
    return "✅ Slack notification sent."


@mcp.tool()
@audited(SCOPE_SCAN_WRITE)
async def notify_teams(message: str, title: str = "SAST Security Notification") -> str:
    """Send a notification to the configured Microsoft Teams incoming webhook.

    Requires the TEAMS_WEBHOOK_URL environment variable.

    Args:
        message: The message body (Markdown supported).
        title: Card title.
    """
    try:
        await _teams_notify(message, title=title)
    except IntegrationError as e:
        return f"Teams notification failed: {e}"
    return "✅ Microsoft Teams notification sent."


@mcp.tool()
@audited(SCOPE_SCAN_WRITE)
async def create_jira_issue(
    project_key: str,
    summary: str,
    description: str,
    issue_type: str = "Bug",
) -> str:
    """Open a Jira issue for a security finding.

    Requires the JIRA_URL, JIRA_EMAIL, and JIRA_API_TOKEN environment variables.

    Args:
        project_key: The Jira project key (e.g. 'SEC').
        summary: Issue title.
        description: Issue description (plain text).
        issue_type: Jira issue type name (default 'Bug').
    """
    try:
        result = await _jira_create(project_key, summary, description, issue_type)
    except IntegrationError as e:
        return f"Jira issue creation failed: {e}"

    key = result.get("key", "")
    return f"✅ Created Jira issue {key}." if key else "✅ Jira issue created."


# ---------------------------------------------------------------------------
# AI Patch Generation
# ---------------------------------------------------------------------------
@mcp.tool()
@audited(SCOPE_SCAN_READ)
async def generate_fix_prompt(
    target_path: str,
    finding_hash: str,
    context_window: int = 15,
) -> str:
    """Build an LLM-ready prompt to fix a cached finding as a unified diff.

    Recovers the finding (by hash) from the scan cache, extracts an expanded
    window of the vulnerable source, and returns a prompt engineered to make
    an LLM emit a strict unified diff. After generating the patch, apply it
    with `apply_patch`.

    Args:
        target_path: Root of the scanned project (must have a `.sast-mcp-cache`).
        finding_hash: Hash of the finding to remediate (shown in scan output).
        context_window: Source lines to include before/after the finding.
    """
    if not os.path.isdir(target_path):
        return f"Error: Target path '{target_path}' is not a valid directory."
    if context_window < 0:
        return "Error: context_window must be >= 0."

    return build_patch_prompt(target_path, finding_hash, context_window)


@mcp.tool()
@audited(SCOPE_SCAN_WRITE)
async def apply_patch(
    target_path: str,
    patch: str,
    check_only: bool = False,
) -> str:
    """Apply an agent-generated unified diff to files under target_path.

    Uses `git apply`, which refuses paths that escape the target directory.
    Run with `check_only=True` first to verify the patch applies cleanly
    before writing changes.

    Args:
        target_path: Directory the patch paths are relative to.
        patch: The unified diff text to apply.
        check_only: If True, validate without modifying any files.
    """
    if not os.path.isdir(target_path):
        return f"Error: Target path '{target_path}' is not a valid directory."

    success, detail = await apply_unified_diff(
        target_path, patch, check_only=check_only, timeout=SCAN_TIMEOUT
    )
    if success:
        return f"✅ {detail}"
    return f"❌ Patch {'check' if check_only else 'apply'} failed:\n{detail}"


# ---------------------------------------------------------------------------
# Closed-loop remediation & SARIF ingestion (v0.8.0)
# ---------------------------------------------------------------------------
async def _scan_path_for_findings(scan_target: str, scanner_name: str):
    """Scan a path with one scanner (or all) and return findings, or None.

    Returns None when the scan can't be performed (scanner missing), so callers
    can distinguish "couldn't verify" from "no findings".
    """
    if scanner_name in ScannerFactory.list_scanners():
        scanner = ScannerFactory.get_scanner(scanner_name)
        try:
            await scanner.check_dependency()
        except RuntimeError:
            return None
        try:
            return await scanner.scan(
                scan_target,
                min_severity="LOW",
                min_confidence="LOW",
                timeout=SCAN_TIMEOUT,
            )
        except RuntimeError:
            return None
    findings, used, _ = await run_all_scanners(
        scan_target, min_severity="LOW", min_confidence="LOW", timeout=SCAN_TIMEOUT
    )
    return findings if used else None


@mcp.tool()
@audited(SCOPE_SCAN_WRITE)
async def remediate_and_verify(
    target_path: str,
    finding_hash: str,
    patch: str,
    scanner_name: str = "",
    auto_rollback: bool = True,
) -> str:
    """Apply a fix and prove it worked: scan → patch → re-scan → confirm gone.

    The closed remediation loop. Recovers the finding by hash, dry-runs the
    patch, re-scans the affected file before and after applying it, and returns
    PASS only if the finding's hash disappears **and** no new finding of equal
    or higher severity is introduced. On failure (and when ``auto_rollback``),
    the patch is reverted so the working tree is left clean.

    Args:
        target_path: Root of the scanned project (with a `.sast-mcp-cache`).
        finding_hash: Hash of the finding to fix (from earlier scan output).
        patch: The unified diff to apply (e.g. produced via generate_fix_prompt).
        scanner_name: Scanner to re-scan with. Defaults to the finding's
            originating scanner, falling back to all scanners.
        auto_rollback: Revert the patch if verification fails (default True).
    """
    if not os.path.isdir(target_path):
        return f"Error: Target path '{target_path}' is not a valid directory."

    cache = ScanCache(target_path)
    finding = cache.find_finding_by_hash(finding_hash)
    if finding is None:
        return (
            f"Error: No cached finding with hash `{finding_hash}`. Run a scan "
            "(e.g. scan_all) first so the finding is cached, then retry."
        )

    scanner_name = (scanner_name or finding.scanner or "").strip()
    scan_target = (
        finding.file
        if os.path.isabs(finding.file)
        else os.path.join(target_path, finding.file)
    )
    if not os.path.exists(scan_target):
        scan_target = target_path

    # 1) Dry-run the patch before touching anything.
    ok, detail = await apply_unified_diff(
        target_path, patch, check_only=True, timeout=SCAN_TIMEOUT
    )
    if not ok:
        return f"❌ FAIL — patch does not apply cleanly:\n{detail}"

    # 2) Baseline scan of the affected file.
    before = await _scan_path_for_findings(scan_target, scanner_name)
    if before is None:
        return (
            "❌ FAIL — could not verify: scanner "
            f"'{scanner_name}' is unavailable to re-scan."
        )
    before_hashes = {f.finding_hash for f in before}

    # 3) Apply the patch.
    ok, detail = await apply_unified_diff(
        target_path, patch, check_only=False, timeout=SCAN_TIMEOUT
    )
    if not ok:
        return f"❌ FAIL — patch failed to apply:\n{detail}"

    # 4) Re-scan and evaluate.
    after = await _scan_path_for_findings(scan_target, scanner_name)
    rolled_back = False
    if after is None:
        verdict_lines = ["⚠️ Patch applied but re-scan failed; cannot verify."]
        fixed = False
        regressions: list = []
    else:
        after_hashes = {f.finding_hash for f in after}
        fixed = finding_hash not in after_hashes
        orig_order = SEVERITY_ORDER.get(finding.severity, 0)
        regressions = [
            f
            for f in after
            if f.finding_hash not in before_hashes
            and SEVERITY_ORDER.get(f.severity, 0) >= orig_order
        ]
        verdict_lines = []

    success = fixed and not regressions and after is not None
    if not success and auto_rollback:
        rb_ok, _rb_detail = await apply_unified_diff(
            target_path, patch, reverse=True, timeout=SCAN_TIMEOUT
        )
        rolled_back = rb_ok

    verdict = "✅ PASS" if success else "❌ FAIL"
    lines = [f"### Remediate & Verify: {verdict}", *verdict_lines]
    lines.append(f"**Finding:** {finding.title} ({finding.severity.value})")
    lines.append(f"**File:** {finding.file}")
    lines.append(f"**Re-scanned with:** {scanner_name or 'all scanners'}")
    lines.append(f"**Finding cleared:** {'yes' if fixed else 'no'}")
    if regressions:
        lines.append(
            f"**Regressions introduced:** {len(regressions)} "
            "(new finding(s) of equal/higher severity)"
        )
        for r in regressions[:5]:
            lines.append(f"- [{r.severity.value}] {r.title} — {r.file}:{r.line_start}")
    if not success and auto_rollback:
        rb_msg = (
            "patch reverted, tree clean"
            if rolled_back
            else "rollback FAILED — inspect the tree"
        )
        lines.append(f"**Rollback:** {rb_msg}")
    elif success:
        lines.append("**Patch retained.** Re-run scan_all to confirm the broader tree.")
    return "\n".join(lines)


@mcp.tool()
@audited(SCOPE_SCAN_WRITE)
async def import_sarif(
    target_path: str,
    sarif_path: str,
    scanner_name: str = "external",
    save: bool = True,
) -> str:
    """Ingest an external SARIF file into the normalized finding pipeline.

    Lets results from any SARIF-producing tool (Snyk, Veracode, CodeQL, a CI
    job, etc.) join the same dedup / baseline / dashboard flow as native scans.
    The findings are re-enriched with AST context and stable hashes on import.

    Args:
        target_path: Project root the SARIF results belong to (for caching).
        sarif_path: Path to a SARIF 2.1.0 JSON file.
        scanner_name: Name to record as the source scanner (default 'external').
        save: Cache the imported findings so compare_baseline / dashboards see
            them (default True).
    """
    if not os.path.isdir(target_path):
        return f"Error: Target path '{target_path}' is not a valid directory."
    if not os.path.isfile(sarif_path):
        return f"Error: SARIF file '{sarif_path}' does not exist."

    try:
        with open(sarif_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        return f"Error reading SARIF: {e}"

    try:
        findings = parse_sarif(data, scanner_name)
    except Exception as e:  # malformed SARIF
        return f"Error parsing SARIF: {e}"

    ignore_manager = IgnoreManager(target_path)
    findings = [f for f in findings if not ignore_manager.is_ignored(f.finding_hash)]

    if save and findings:
        ScanCache(target_path).save_scan(scanner_name, findings)

    counts: dict[str, int] = {level.value: 0 for level in SeverityLevel}
    for f in findings:
        counts[f.severity.value] += 1

    return (
        f"✅ Imported {len(findings)} finding(s) from "
        f"`{os.path.basename(sarif_path)}` as scanner `{scanner_name}`.\n"
        + ", ".join(f"{sev}={counts[sev]}" for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"])
        + (
            f"\nCached — use compare_baseline / dashboards with scanner "
            f"`{scanner_name}`."
            if save and findings
            else ""
        )
    )


@mcp.tool()
@audited(SCOPE_CONFIG_WRITE)
async def triage_finding(
    target_path: str,
    finding_hash: str,
    disposition: str = "",
    justification: str = "",
) -> str:
    """Triage a finding: get an exploitability prompt, or record a VEX decision.

    Two modes:
      * **No disposition** — returns an LLM-ready prompt to assess whether the
        finding is exploitable / a false positive in this codebase.
      * **With a disposition** (`exploitable`, `not_affected`, `false_positive`,
        `resolved`, `in_triage`) — records a CycloneDX VEX statement. Suppressing
        dispositions also add the finding to the ignore-list with the rationale.

    Args:
        target_path: Root of the scanned project (with a `.sast-mcp-cache`).
        finding_hash: Hash of the finding to triage.
        disposition: VEX state keyword (empty = return a triage prompt instead).
        justification: Rationale (CycloneDX justification keyword for
            not_affected, otherwise free text).
    """
    if not os.path.isdir(target_path):
        return f"Error: Target path '{target_path}' is not a valid directory."

    cache = ScanCache(target_path)
    finding = cache.find_finding_by_hash(finding_hash)
    if finding is None:
        return (
            f"Error: No cached finding with hash `{finding_hash}`. Run a scan "
            "first so the finding is cached, then retry."
        )

    if not disposition.strip():
        return (
            "You are a senior application security engineer. Assess whether the "
            "following finding is genuinely exploitable in this codebase or a "
            "false positive, and recommend a disposition.\n\n"
            f"## Finding\n"
            f"- **Title:** {finding.title}\n"
            f"- **Severity:** {finding.severity.value}\n"
            f"- **Confidence:** {finding.confidence.value}\n"
            f"- **Scanner:** {finding.scanner}\n"
            f"- **Location:** {finding.file}:{finding.line_start}-{finding.line_end}\n"
            f"- **CWE:** {finding.cwe or 'n/a'}\n"
            f"- **Hash:** {finding_hash}\n\n"
            f"## Description\n{finding.message or '(no scanner message)'}\n\n"
            f"## Code context\n```{finding.language}\n{finding.context}\n```\n\n"
            "## Decide\n"
            "1. Is the vulnerable code reachable with attacker-controlled input?\n"
            "2. Are there mitigating controls already in place?\n"
            "3. Recommend one disposition: `exploitable`, `not_affected`, or "
            "`false_positive`, with a one-line justification.\n"
            "4. Record it by calling `triage_finding` again with that "
            "`disposition` and `justification`."
        )

    state = normalize_disposition(disposition)
    if state is None:
        return (
            f"Error: unknown disposition '{disposition}'. Valid: exploitable, "
            "not_affected, false_positive, resolved, in_triage."
        )

    vex_entry = build_vex_statement(finding, disposition, justification)
    vex_doc = findings_to_vex([vex_entry], __version__)

    suppressed = ""
    if disposition.lower().strip() in SUPPRESSING_DISPOSITIONS:
        IgnoreManager(target_path).ignore(
            finding_hash, reason=f"{disposition}: {justification}".strip(": ")
        )
        suppressed = (
            f"\nFinding added to the ignore-list "
            f"(`{target_path}/.sast-mcp-ignore.json`); future scans will hide it."
        )

    return (
        f"✅ Recorded VEX disposition `{state}` for `{finding.title}`.{suppressed}\n\n"
        f"### CycloneDX VEX\n```json\n{json.dumps(vex_doc, indent=2)}\n```"
    )


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="sast-mcp-server",
        description="SAST MCP Server — Static Application Security Testing for AI agents",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help=(
            "Transport protocol: 'stdio' for local agents (default), "
            "'streamable-http' for production HTTP (recommended), "
            "'sse' for legacy HTTP/SSE (deprecated)."
        ),
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind the HTTP server to (default: 0.0.0.0).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port for the HTTP server (default: 8080).",
    )
    parser.add_argument(
        "--stateless",
        action="store_true",
        help="Run in stateless mode for horizontally-scaled deployments.",
    )
    return parser.parse_args()


def _validate_auth() -> AuthProvider:
    """Initialize and validate authentication.

    Supports:
    - Simple API key via SAST_MCP_API_KEY (backward-compatible)
    - JWT tokens via SAST_MCP_JWT_SECRET
    - No auth (for local stdio transport)

    Returns:
        Configured AuthProvider instance.
    """
    auth = AuthProvider()
    status = auth.get_status()

    if status["enabled"]:
        logger.info(
            "Authentication ENABLED (mode: %s)", status["mode"]
        )
    else:
        logger.info(
            "Authentication DISABLED. "
            "Set SAST_MCP_API_KEY or SAST_MCP_JWT_SECRET for remote deployments."
        )

    return auth


async def _check_scanner_availability() -> tuple[list[str], list[str]]:
    """Return (available, missing) scanner names by probing check_dependency()."""
    available = await _probe_installed_scanners()
    available_set = set(available)
    missing = sorted(n for n in ScannerFactory.list_scanners() if n not in available_set)
    return available, missing


def _log_scanner_availability() -> None:
    """Log a one-line summary of which scanners are usable in this environment.

    Goes to stderr (via the configured logger) so the stdio transport stays clean.
    Helps users immediately see how much of the toolset they actually have.
    """
    try:
        available, missing = asyncio.run(_check_scanner_availability())
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Scanner availability probe failed: %s", exc)
        return
    total = len(available) + len(missing)
    logger.info(
        "Scanners available: %d/%d (%s)%s",
        len(available),
        total,
        ", ".join(available) if available else "none",
        f" | missing: {', '.join(missing)}" if missing else "",
    )
    if not available:
        logger.warning(
            "No scanners are installed — scan tools will return errors. "
            "Use the full Docker image (ghcr.io/skyrxin/sast-mcp-server:full) "
            'or install the pip extra: pip install "sast-mcp-server[scanners]".'
        )


def main():
    """Entry point for the MCP server.

    Supports three transport modes:
    - stdio (default): For local agent integrations (Gemini CLI, Claude Desktop, etc.)
    - streamable-http: For production HTTP deployments (recommended)
    - sse: Legacy HTTP/SSE transport (deprecated)

    Environment variables:
        SAST_MCP_API_KEY: Static API key for authentication
        SAST_MCP_JWT_SECRET: HMAC-SHA256 secret for JWT token validation
        SAST_MCP_TIMEOUT: Scan timeout in seconds (default: 300)
        SAST_MCP_LOG_LEVEL: Logging level (default: INFO)
        SAST_MCP_CACHE_TTL: Cache time-to-live in seconds (default: 86400)
    """
    args = _parse_args()
    auth = _validate_auth()

    logger.info(
        "Starting SAST MCP Server v%s (transport=%s)",
        __version__,
        args.transport,
    )
    _log_scanner_availability()

    if args.transport == "streamable-http":
        if not auth.auth_enabled:
            logger.warning(
                "⚠️  Running Streamable HTTP server WITHOUT authentication. "
                "Set SAST_MCP_JWT_SECRET or SAST_MCP_API_KEY "
                "for production deployments."
            )
        logger.info(
            "Streamable HTTP server listening on http://%s:%d/mcp",
            args.host,
            args.port,
        )
        mcp.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
        )
    elif args.transport == "sse":
        warnings.warn(
            "SSE transport is deprecated. "
            "Use --transport streamable-http instead.",
            DeprecationWarning,
            stacklevel=1,
        )
        logger.warning(
            "⚠️  SSE transport is DEPRECATED. "
            "Migrate to --transport streamable-http."
        )
        if not auth.auth_enabled:
            logger.warning(
                "⚠️  Running SSE server WITHOUT authentication."
            )
        logger.info(
            "SSE server listening on http://%s:%d",
            args.host,
            args.port,
        )
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
