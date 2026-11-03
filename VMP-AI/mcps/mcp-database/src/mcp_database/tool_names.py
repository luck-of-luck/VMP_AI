from __future__ import annotations

import json
from collections.abc import Mapping

from .errors import ConfigError

# Canonical inventory of every tool the server registers. A test asserts the built server matches this
# set exactly, so it cannot drift when a tool is added or removed.
ALL_TOOL_NAMES = frozenset(
    {
        "db_schema_connections",
        "db_schema_databases",
        "db_schema_objects",
        "db_schema_describe",
        "db_schema_ddl",
        "db_schema_search",
        "db_schema_relationships",
        "db_schema_users",
        "db_schema_grants",
        "db_schema_search_indexes",
        "db_read_query",
        "db_read_sample",
        "db_read_export",
        "db_read_vector_search",
        "db_read_text_search",
        "db_perf_explain",
        "db_perf_top_queries",
        "db_perf_active_ops",
        "db_perf_blocking",
        "db_perf_index_stats",
        "db_perf_table_stats",
        "db_perf_column_stats",
        "db_perf_diagnose",
        "db_perf_health",
        "db_perf_replication",
        "db_perf_settings",
        "db_perf_logs",
        "db_perf_vector_stats",
        "db_perf_cluster",
        "db_perf_storage",
        "db_perf_tls",
        "db_perf_config_check",
        "db_perf_index_advisor",
        "db_write_query",
        "db_write_search_index",
        "db_admin_kill",
        "db_admin_analyze",
        "db_admin_maintain",
        "db_admin_cluster",
    }
)


def _parse_name_list(value: str, var: str) -> list[str]:
    """Parse a JSON array of tool-name strings, or a clear config error."""
    try:
        names = json.loads(value)
    except json.JSONDecodeError:
        raise ConfigError(f'{var} must be a JSON array of tool names, e.g. ["db_read_query"]') from None
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise ConfigError(f"{var} must be a JSON array of tool-name strings")
    return names


def resolve_enabled_tools(env: Mapping[str, str]) -> frozenset[str] | None:
    """The tools to expose from TOOLS (allowlist) / DISABLE_TOOLS (denylist); None means every tool.

    The two are mutually exclusive; unknown names and lists that would expose nothing are rejected.
    """
    allow = env.get("TOOLS")
    deny = env.get("DISABLE_TOOLS")
    if allow and deny:
        raise ConfigError("Set only one of TOOLS (allowlist) or DISABLE_TOOLS (denylist), not both")
    if allow:
        names = _parse_name_list(allow, "TOOLS")
        if not names:
            raise ConfigError("TOOLS is empty; list at least one tool, or omit it to expose all")
        unknown = sorted(set(names) - ALL_TOOL_NAMES)
        if unknown:
            raise ConfigError(f"TOOLS lists unknown tools: {', '.join(unknown)}")
        return frozenset(names)
    if deny:
        names = _parse_name_list(deny, "DISABLE_TOOLS")
        unknown = sorted(set(names) - ALL_TOOL_NAMES)
        if unknown:
            raise ConfigError(f"DISABLE_TOOLS lists unknown tools: {', '.join(unknown)}")
        enabled = ALL_TOOL_NAMES - set(names)
        if not enabled:
            raise ConfigError("DISABLE_TOOLS disables every tool; leave at least one enabled")
        return enabled
    return None
