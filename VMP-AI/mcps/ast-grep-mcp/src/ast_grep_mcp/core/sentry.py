"""Sentry error tracking integration for ast-grep MCP server."""

import os
from typing import Any

import sentry_sdk
from sentry_sdk.integrations.anthropic import AnthropicIntegration

from ast_grep_mcp.constants import LoggingDefaults, SentryDefaults
from ast_grep_mcp.core.logging import get_logger

# Re-export capture_exception for backward compatibility


def _make_tag_event(service_name: str) -> Any:
    """Return a before_send callback that tags every event with service info."""

    def _tag_event(event: Any, hint: Any) -> Any:
        event.setdefault("tags", {})
        event["tags"]["service"] = service_name
        event["tags"]["language"] = "python"
        event["tags"]["component"] = "mcp-server"
        return event

    return _tag_event


def _sentry_init(dsn: str, service_name: str, sentry_env: str) -> None:
    """Call sentry_sdk.init with the resolved configuration."""
    is_dev = sentry_env == "development"
    sentry_sdk.init(
        dsn=dsn,
        environment=sentry_env,
        integrations=[AnthropicIntegration(include_prompts=True)],
        traces_sample_rate=1.0 if is_dev else SentryDefaults.PRODUCTION_TRACES_SAMPLE_RATE,
        profiles_sample_rate=1.0 if is_dev else SentryDefaults.PRODUCTION_PROFILES_SAMPLE_RATE,
        send_default_pii=True,
        attach_stacktrace=True,
        max_breadcrumbs=LoggingDefaults.MAX_BREADCRUMBS,
        debug=is_dev,
        before_send=_make_tag_event(service_name),
    )


def init_sentry(service_name: str = "ast-grep-mcp") -> None:
    """Initialize Sentry with Anthropic AI integration and service tagging.

    Args:
        service_name: Unique service identifier (default: 'ast-grep-mcp')
    """
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return

    sentry_env = os.getenv("SENTRY_ENVIRONMENT", "development")
    _sentry_init(dsn, service_name, sentry_env)

    sentry_sdk.set_tag("service", service_name)
    sentry_sdk.set_tag("language", "python")
    sentry_sdk.set_tag("component", "mcp-server")

    logger = get_logger("sentry")
    logger.info("sentry_initialized", service=service_name, environment=sentry_env)
