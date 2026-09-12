"""CROWORK tools — salas colaborativas compartilhadas."""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

from hermes_constants import get_hermes_home


def _crowork_dir() -> Path:
    p = get_hermes_home() / "crowork"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _room_file(room: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in room) or "default"
    return _crowork_dir() / f"{safe}.json"


def _load_room(room: str) -> dict:
    f = _room_file(room)
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_room(room: str, data: dict):
    _room_file(room).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _check_crowork_available() -> bool:
    return True


# Schemas
CROWORK_CREATE_SCHEMA = {
    "name": "crowork_create",
    "description": "Cria uma sala CROWORK compartilhada (ex: sala-01). Retorna ID e convite.",
    "parameters": {
        "type": "object",
        "properties": {
            "room": {
                "type": "string",
                "description": "Nome da sala (ex: ampliagro-sprint)",
            },
            "topic": {"type": "string", "description": "Tópico/descrição da sala"},
            "share": {
                "type": "boolean",
                "description": "Se true, gera link de convite",
            },
        },
        "required": ["room"],
    },
}

CROWORK_JOIN_SCHEMA = {
    "name": "crowork_join",
    "description": "Entra em uma sala CROWORK existente. Espelha transcript e PTY.",
    "parameters": {
        "type": "object",
        "properties": {
            "room": {"type": "string", "description": "Nome da sala"},
        },
        "required": ["room"],
    },
}

CROWORK_LIST_SCHEMA = {
    "name": "crowork_list",
    "description": "Lista salas CROWORK ativas neste HERMES_HOME.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}

CROWORK_STATUS_SCHEMA = {
    "name": "crowork_status",
    "description": "Mostra status da sala CROWORK (membros, presença, tópico).",
    "parameters": {
        "type": "object",
        "properties": {"room": {"type": "string", "description": "Nome da sala"}},
        "required": ["room"],
    },
}

CROWORK_LEAVE_SCHEMA = {
    "name": "crowork_leave",
    "description": "Sai da sala CROWORK atual.",
    "parameters": {
        "type": "object",
        "properties": {"room": {"type": "string"}},
        "required": ["room"],
    },
}

CROWORK_SHARE_SCHEMA = {
    "name": "crowork_share",
    "description": "Gera link/convite para compartilhar sala CROWORK (copiar para coworker).",
    "parameters": {
        "type": "object",
        "properties": {"room": {"type": "string"}},
        "required": ["room"],
    },
}


def _handle_crowork_create(args, **kw) -> str:
    room = args.get("room", "default").strip() or "default"
    topic = args.get("topic", "")
    share = bool(args.get("share", True))
    data = _load_room(room)
    if data.get("created_at"):
        # already exists - return existing
        return json.dumps(
            {"success": True, "room": room, "already_exists": True, "data": data},
            ensure_ascii=False,
        )
    data = {
        "room": room,
        "id": str(uuid.uuid4())[:8],
        "topic": topic,
        "created_at": int(time.time()),
        "created_at_human": time.strftime("%Y-%m-%d %H:%M:%S"),
        "members": [],
        "presence": {},
        "topic_history": [topic] if topic else [],
        "share_link": f"hermes crowork join {room}" if share else "",
    }
    _save_room(room, data)
    return json.dumps(
        {
            "success": True,
            "room": room,
            "data": data,
            "hint": "Use crowork_join para entrar. PTY espelhado via tui_gateway.",
        },
        ensure_ascii=False,
    )


def _handle_crowork_join(args, **kw) -> str:
    room = args.get("room", "default").strip() or "default"
    data = _load_room(room)
    if not data:
        return json.dumps(
            {
                "success": False,
                "error": f"Sala '{room}' não existe. Use crowork_create primeiro.",
            },
            ensure_ascii=False,
        )
    # add member presence (lightweight)
    member = kw.get("task_id") or os.environ.get("HERMES_PROFILE", "local")
    data.setdefault("members", [])
    if member not in data["members"]:
        data["members"].append(str(member))
    data["presence"][str(member)] = int(time.time())
    data["last_join"] = int(time.time())
    _save_room(room, data)
    return json.dumps(
        {
            "success": True,
            "room": room,
            "data": data,
            "hint": "Transcript compartilhado. Use /crowork status para ver quem está online.",
        },
        ensure_ascii=False,
    )


def _handle_crowork_list(args, **kw) -> str:
    d = _crowork_dir()
    rooms = []
    for p in d.glob("*.json"):
        try:
            j = json.loads(p.read_text(encoding="utf-8"))
            rooms.append({
                "room": j.get("room", p.stem),
                "topic": j.get("topic", ""),
                "members": len(j.get("members", [])),
                "created_at": j.get("created_at_human", ""),
            })
        except Exception:
            continue
    return json.dumps(
        {"success": True, "rooms": rooms, "count": len(rooms)}, ensure_ascii=False
    )


def _handle_crowork_status(args, **kw) -> str:
    room = args.get("room", "default")
    data = _load_room(room)
    if not data:
        return json.dumps(
            {"success": False, "error": f"Sala '{room}' não encontrada"},
            ensure_ascii=False,
        )
    # presence TTL 5 min
    now = int(time.time())
    active = {k: v for k, v in data.get("presence", {}).items() if now - v < 300}
    data["active_members"] = list(active.keys())
    return json.dumps({"success": True, "room": room, "data": data}, ensure_ascii=False)


def _handle_crowork_leave(args, **kw) -> str:
    room = args.get("room", "default")
    data = _load_room(room)
    if not data:
        return json.dumps(
            {"success": False, "error": "Sala não encontrada"}, ensure_ascii=False
        )
    member = kw.get("task_id") or os.environ.get("HERMES_PROFILE", "local")
    data.get("members", []).remove(str(member)) if str(member) in data.get(
        "members", []
    ) else None
    data.get("presence", {}).pop(str(member), None)
    _save_room(room, data)
    return json.dumps(
        {"success": True, "room": room, "left": str(member)}, ensure_ascii=False
    )


def _handle_crowork_share(args, **kw) -> str:
    room = args.get("room", "default")
    data = _load_room(room)
    if not data:
        return json.dumps(
            {"success": False, "error": "Sala não existe"}, ensure_ascii=False
        )
    link = data.get("share_link") or f"hermes crowork join {room}"
    inv = f"Convite CROWORK: sala '{room}' | tópico: {data.get('topic', '')} | comando: {link} | id: {data.get('id')}"
    return json.dumps(
        {"success": True, "room": room, "share_link": link, "invite_text": inv},
        ensure_ascii=False,
    )
