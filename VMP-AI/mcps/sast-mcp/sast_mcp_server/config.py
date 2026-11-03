"""Central, validated configuration for the SAST MCP Server.

All runtime configuration is read from environment variables exactly once, here,
into a single ``Settings`` object. Modules should import :data:`settings` (or call
:func:`get_settings`) instead of calling ``os.environ.get`` directly, so values are
parsed and bounds-checked in one place.

Secrets (auth keys, integration tokens) are intentionally surfaced as properties
that read the environment live, so rotating a credential does not require a
restart and the value never has to be cached in memory longer than a request.
"""

import json
import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

logger = logging.getLogger(__name__)

# Environment variable names (single source of truth).
ENV_TIMEOUT = "SAST_MCP_TIMEOUT"
ENV_LOG_LEVEL = "SAST_MCP_LOG_LEVEL"
ENV_CACHE_TTL = "SAST_MCP_CACHE_TTL"
ENV_HTTP_RETRIES = "SAST_MCP_HTTP_RETRIES"
ENV_HTTP_TIMEOUT = "SAST_MCP_HTTP_TIMEOUT"
ENV_CACHE_MAX_SCANS = "SAST_MCP_CACHE_MAX_SCANS"
ENV_MAX_CONCURRENT_SCANS = "SAST_MCP_MAX_CONCURRENT_SCANS"
ENV_RATE_LIMIT_PER_MIN = "SAST_MCP_RATE_LIMIT_PER_MIN"
ENV_SCANNER_TIMEOUTS = "SAST_MCP_SCANNER_TIMEOUTS"

ENV_API_KEY = "SAST_MCP_API_KEY"
ENV_JWT_SECRET = "SAST_MCP_JWT_SECRET"

# Defaults
DEFAULT_TIMEOUT = 300
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_CACHE_TTL = 86400
DEFAULT_HTTP_RETRIES = 3
DEFAULT_HTTP_TIMEOUT = 60.0
DEFAULT_CACHE_MAX_SCANS = 200
# 0 = unlimited concurrency; otherwise bound simultaneous subprocess scanners.
DEFAULT_MAX_CONCURRENT_SCANS = 8
# 0 = rate limiting disabled (the default; stdio never rate-limits).
DEFAULT_RATE_LIMIT_PER_MIN = 0

_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def _scanner_timeouts_env(name: str) -> dict[str, int]:
    """Parse an optional JSON map of ``{scanner: timeout_seconds}`` from env.

    Invalid JSON or non-positive values are ignored with a warning, so a bad
    override can never crash startup or shorten a timeout below 1s.
    """
    raw = os.environ.get(name)
    if not raw or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        logger.warning("%s=%r is not valid JSON; ignoring", name, raw)
        return {}
    if not isinstance(parsed, dict):
        logger.warning("%s must be a JSON object; ignoring", name)
        return {}
    result: dict[str, int] = {}
    for scanner, value in parsed.items():
        try:
            seconds = int(value)
        except (ValueError, TypeError):
            logger.warning("%s[%s]=%r is not an integer; skipping", name, scanner, value)
            continue
        if seconds < 1:
            logger.warning("%s[%s]=%d below 1s; skipping", name, scanner, seconds)
            continue
        result[str(scanner)] = seconds
    return result


def _int_env(name: str, default: int, minimum: int = 1, maximum: int | None = None) -> int:
    """Read a bounded integer env var, falling back to ``default`` on bad input."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        logger.warning("%s=%r is not an integer; using default %d", name, raw, default)
        return default
    if value < minimum:
        logger.warning("%s=%d below minimum %d; clamping", name, value, minimum)
        value = minimum
    if maximum is not None and value > maximum:
        logger.warning("%s=%d above maximum %d; clamping", name, value, maximum)
        value = maximum
    return value


def _float_env(name: str, default: float, minimum: float = 0.1) -> float:
    """Read a bounded float env var, falling back to ``default`` on bad input."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw.strip())
    except ValueError:
        logger.warning("%s=%r is not a number; using default %s", name, raw, default)
        return default
    if value < minimum:
        logger.warning("%s=%s below minimum %s; clamping", name, value, minimum)
        value = minimum
    return value


@dataclass(frozen=True)
class Settings:
    """Validated server settings, loaded once from the environment."""

    scan_timeout: int
    log_level: str
    cache_ttl: int
    http_retries: int
    http_timeout: float
    cache_max_scans: int
    max_concurrent_scans: int
    rate_limit_per_min: int
    scanner_timeouts: Mapping[str, int] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "Settings":
        """Build a Settings object from the current environment, with validation."""
        log_level = os.environ.get(ENV_LOG_LEVEL, DEFAULT_LOG_LEVEL).upper().strip()
        if log_level not in _VALID_LOG_LEVELS:
            logger.warning(
                "%s=%r is not a valid level; using %s",
                ENV_LOG_LEVEL,
                log_level,
                DEFAULT_LOG_LEVEL,
            )
            log_level = DEFAULT_LOG_LEVEL

        return cls(
            scan_timeout=_int_env(ENV_TIMEOUT, DEFAULT_TIMEOUT, minimum=1),
            log_level=log_level,
            cache_ttl=_int_env(ENV_CACHE_TTL, DEFAULT_CACHE_TTL, minimum=0),
            http_retries=_int_env(ENV_HTTP_RETRIES, DEFAULT_HTTP_RETRIES, minimum=0, maximum=10),
            http_timeout=_float_env(ENV_HTTP_TIMEOUT, DEFAULT_HTTP_TIMEOUT),
            cache_max_scans=_int_env(
                ENV_CACHE_MAX_SCANS, DEFAULT_CACHE_MAX_SCANS, minimum=0
            ),
            max_concurrent_scans=_int_env(
                ENV_MAX_CONCURRENT_SCANS, DEFAULT_MAX_CONCURRENT_SCANS, minimum=0
            ),
            rate_limit_per_min=_int_env(
                ENV_RATE_LIMIT_PER_MIN, DEFAULT_RATE_LIMIT_PER_MIN, minimum=0
            ),
            scanner_timeouts=MappingProxyType(_scanner_timeouts_env(ENV_SCANNER_TIMEOUTS)),
        )

    # --- Live secret accessors (read on demand, never cached) ---
    @property
    def api_key(self) -> str:
        """Static API key for legacy auth (empty string if unset)."""
        return os.environ.get(ENV_API_KEY, "").strip()

    @property
    def jwt_secret(self) -> str:
        """HMAC-SHA256 secret for JWT auth (empty string if unset)."""
        return os.environ.get(ENV_JWT_SECRET, "").strip()


# Module-level singleton, loaded at import time.
settings = Settings.from_env()


def get_settings() -> Settings:
    """Return the process-wide :class:`Settings` singleton."""
    return settings
