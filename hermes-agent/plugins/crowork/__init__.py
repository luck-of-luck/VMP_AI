"""CROWORK plugin — salas colaborativas.

Plugin standalone que registra 6 tools no toolset crowork:
crowork_create / join / list / status / leave / share

Por que plugin e não tools/ ?
- Capacidade de borda (colaboração) — não é core tool de todo turno.
- Toolset crowork só aparece quando explicitamente habilitado ou via CLI /crowork
- Segue padrão spotify / image_gen: plugin auto-loaded, kind: backend
"""

from __future__ import annotations

from plugins.crowork.tools import (
    CROWORK_CREATE_SCHEMA,
    CROWORK_JOIN_SCHEMA,
    CROWORK_LEAVE_SCHEMA,
    CROWORK_LIST_SCHEMA,
    CROWORK_SHARE_SCHEMA,
    CROWORK_STATUS_SCHEMA,
    _check_crowork_available,
    _handle_crowork_create,
    _handle_crowork_join,
    _handle_crowork_leave,
    _handle_crowork_list,
    _handle_crowork_share,
    _handle_crowork_status,
)

_TOOLS = (
    ("crowork_create", CROWORK_CREATE_SCHEMA, _handle_crowork_create, "👥"),
    ("crowork_join", CROWORK_JOIN_SCHEMA, _handle_crowork_join, "🚪"),
    ("crowork_list", CROWORK_LIST_SCHEMA, _handle_crowork_list, "📋"),
    ("crowork_status", CROWORK_STATUS_SCHEMA, _handle_crowork_status, "👀"),
    ("crowork_leave", CROWORK_LEAVE_SCHEMA, _handle_crowork_leave, "👋"),
    ("crowork_share", CROWORK_SHARE_SCHEMA, _handle_crowork_share, "🔗"),
)


def register(ctx) -> None:
    for name, schema, handler, emoji in _TOOLS:
        ctx.register_tool(
            name=name,
            toolset="crowork",
            schema=schema,
            handler=handler,
            check_fn=_check_crowork_available,
            emoji=emoji,
        )
