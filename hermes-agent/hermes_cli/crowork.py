"""hermes crowork — sala colaborativa compartilhada (CLI)."""

from __future__ import annotations

import json
import time
from pathlib import Path

from hermes_constants import get_hermes_home, display_hermes_home


def _dir() -> Path:
    p = get_hermes_home() / "crowork"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _file(room: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in room) or "default"
    return _dir() / f"{safe}.json"


def _load(room: str) -> dict:
    f = _file(room)
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(room: str, data: dict):
    _file(room).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def handle_crowork(args: list[str]) -> str:
    if not args:
        return _help()
    cmd = args[0].lower()
    if cmd in ("create", "new"):
        room = args[1] if len(args) > 1 else "default"
        topic = " ".join(args[2:]) if len(args) > 2 else ""
        return _create(room, topic)
    if cmd in ("join", "enter"):
        room = args[1] if len(args) > 1 else "default"
        return _join(room)
    if cmd in ("leave", "exit", "quit"):
        room = args[1] if len(args) > 1 else "default"
        return _leave(room)
    if cmd in ("list", "ls", "rooms"):
        return _list()
    if cmd in ("status", "show", "info"):
        room = args[1] if len(args) > 1 else "default"
        return _status(room)
    if cmd in ("share", "invite", "link"):
        room = args[1] if len(args) > 1 else "default"
        return _share(room)
    if cmd in ("help", "-h", "--help"):
        return _help()
    return f"Comando crowork desconhecido: {cmd}\n" + _help()


def _help() -> str:
    return (
        "Uso: hermes crowork <comando> [sala] [args]\n"
        "  create <sala> [tópico]  - Cria sala compartilhada\n"
        "  join <sala>             - Entra na sala (espelha transcript/PTY)\n"
        "  leave <sala>            - Sai da sala\n"
        "  list                    - Lista salas\n"
        "  status <sala>           - Status e presença\n"
        "  share <sala>            - Gera convite\n"
        f"Dados em: {display_hermes_home()}/crowork/\n"
        'Aliases: crow, cw | Ex: hermes crowork create ampliagro-sprint "Sprint Agro 5.0"\n'
        "TUI: /crowork create sala-01 | Web: /cowork | Desktop: plugin hermes-crowork\n"
    )


def _create(room: str, topic: str) -> str:
    data = _load(room)
    if data.get("created_at"):
        return f"Sala '{room}' já existe (id={data.get('id')}). Use: hermes crowork join {room}"
    import uuid

    data = {
        "room": room,
        "id": str(uuid.uuid4())[:8],
        "topic": topic,
        "created_at": int(time.time()),
        "created_at_human": time.strftime("%Y-%m-%d %H:%M:%S"),
        "members": [],
        "presence": {},
        "topic_history": [topic] if topic else [],
        "share_link": f"hermes crowork join {room}",
    }
    _save(room, data)
    return f"✅ CROWORK criada: '{room}' (id={data['id']}) tópico='{topic}'\nConvite: hermes crowork join {room}\nTUI: /crowork join {room}  |  Web: abra Cowork Board e selecione '{room}'"


def _join(room: str) -> str:
    data = _load(room)
    if not data:
        return f"❌ Sala '{room}' não existe. Crie com: hermes crowork create {room}"
    import os

    member = os.environ.get("HERMES_PROFILE", "local")
    data.setdefault("members", [])
    if member not in data["members"]:
        data["members"].append(member)
    data.setdefault("presence", {})[member] = int(time.time())
    data["last_join"] = int(time.time())
    _save(room, data)
    return f"🚪 Entrou em '{room}' como {member} (membros: {len(data['members'])})\nTranscript compartilhado via tui_gateway. Use: hermes crowork status {room}"


def _leave(room: str) -> str:
    import os

    data = _load(room)
    if not data:
        return f"❌ Sala '{room}' não encontrada"
    member = os.environ.get("HERMES_PROFILE", "local")
    if member in data.get("members", []):
        data["members"].remove(member)
    data.get("presence", {}).pop(member, None)
    _save(room, data)
    return f"👋 Saiu de '{room}' ({member})"


def _list() -> str:
    d = _dir()
    files = list(d.glob("*.json"))
    if not files:
        return "Nenhuma sala CROWORK. Crie com: hermes crowork create <sala>"
    out = ["Salas CROWORK:"]
    for p in files:
        j = _load(p.stem)
        out.append(
            f"  • {j.get('room', p.stem):20} id={j.get('id', '?'):8} membros={len(j.get('members', []))} tópico='{j.get('topic', '')}'"
        )
    return "\n".join(out)


def _status(room: str) -> str:
    data = _load(room)
    if not data:
        return f"❌ Sala '{room}' não encontrada"
    now = int(time.time())
    active = [k for k, v in data.get("presence", {}).items() if now - v < 300]
    return (
        f"Sala: {room} (id={data.get('id')})\n"
        f"Tópico: {data.get('topic', '')}\n"
        f"Criada: {data.get('created_at_human', '')}\n"
        f"Membros: {', '.join(data.get('members', [])) or '(vazio)'}\n"
        f"Ativos (5min): {', '.join(active) or '(nenhum)'}\n"
        f"Convite: hermes crowork join {room}\n"
    )


def _share(room: str) -> str:
    data = _load(room)
    if not data:
        return f"❌ Sala '{room}' não existe"
    link = data.get("share_link", f"hermes crowork join {room}")
    return f"🔗 Convite CROWORK\nSala: {room}\nID: {data.get('id')}\nTópico: {data.get('topic', '')}\nComando: {link}\nEnvie este texto ao coworker."
