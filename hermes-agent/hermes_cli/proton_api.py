"""PROTON v3 — backend mínimo do buffer-arquivo + upload + supervisor.

Montado em hermes_cli/web_server.py com o mesmo auth do /api/pty.
Tudo fail-silencioso: PROTON funciona mockado/offline sem gateway.

Endpoints:
  POST /api/proton/buffer       {text} ou chunks {?chunk=i&total=n} -> crowork_buffer/prompt.md
  POST /api/proton/upload       multipart file -> images/ ou crowork_buffer/att/ -> {path, url, kind}
  POST /api/proton/apply-skills {model, skills[]} -> crowork_buffer/skills-applied.json (+ patch sugerido)
  GET  /api/proton/health       {mcp, ollama, buffer_bytes}
"""

import json
import time
import urllib.request
from pathlib import Path

try:
    from hermes_cli.config import get_hermes_home
except Exception:  # pragma: no cover — fallback p/ teste isolado
    from pathlib import Path as _P

    def get_hermes_home():  # type: ignore
        import os

        return _P(os.environ.get("HERMES_HOME", str(_P.cwd())))


def _home() -> Path:
    return Path(get_hermes_home())


def _buffer_dir() -> Path:
    d = _home() / "crowork_buffer"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _images_dir() -> Path:
    d = _home() / "images"
    d.mkdir(parents=True, exist_ok=True)
    return d


# Chunk assembly em memória (por processo): {key: {total, parts{}}}
_CHUNKS: dict = {}


def save_buffer(text: str, chunk: int = 0, total: int = 1, key: str = "prompt") -> dict:
    """Salva buffer-arquivo. Suporta cola gigante via chunks de ~50k."""
    if total > 1:
        slot = _CHUNKS.setdefault(key, {"total": total, "parts": {}})
        slot["total"] = total
        slot["parts"][chunk] = text
        if len(slot["parts"]) < total:
            return {
                "status": "chunk_ok",
                "received": len(slot["parts"]),
                "total": total,
            }
        text = "".join(slot["parts"][i] for i in range(total))
        _CHUNKS.pop(key, None)
    # Limite generoso de arquivo (20MB texto) — nunca truncar silenciosamente
    raw = text.encode("utf-8", errors="replace")
    if len(raw) > 20 * 1024 * 1024:
        return {"status": "too_large", "bytes": len(raw), "max_bytes": 20 * 1024 * 1024}
    target = _buffer_dir() / f"{key}.md"
    target.write_text(text, encoding="utf-8")
    return {
        "status": "ok",
        "path": str(target),
        "bytes": len(raw),
        "chars": len(text),
        "lines": text.count("\n") + 1,
    }


def save_upload(filename: str, data: bytes, content_type: str = "") -> dict:
    """Salva anexo. Imagens -> images/, resto -> crowork_buffer/att/. Retorna link direto."""
    safe = (
        "".join(c for c in (filename or "arquivo") if c.isalnum() or c in "._- ")[:80]
        or "arquivo"
    )
    stamp = time.strftime("%Y%m%d-%H%M%S")
    is_image = (content_type or "").startswith("image/") or safe.lower().endswith((
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".bmp",
        ".svg",
    ))
    dest_dir = _images_dir() if is_image else (_buffer_dir() / "att")
    dest_dir.mkdir(parents=True, exist_ok=True)
    # 100MB hard cap p/ anexo (evita OOM no gateway compartilhado)
    if len(data) > 100 * 1024 * 1024:
        return {"status": "too_large", "bytes": len(data)}
    target = dest_dir / f"{stamp}-{safe}"
    target.write_bytes(data)
    kind = "image" if is_image else "file"
    if is_image:
        md_link = f"![{safe}](hermes-images://{target.name})"
    else:
        md_link = f"[{safe}](hermes-file://{target.name})"
    return {
        "status": "ok",
        "path": str(target),
        "name": target.name,
        "kind": kind,
        "bytes": len(data),
        "md_link": md_link,
    }


def apply_skills(model: str, skills: list) -> dict:
    """Valida skills contra hermes-agent/skills/ e registra escolha por IA ativa."""
    if not isinstance(skills, list):
        return {"status": "error", "message": "skills deve ser lista"}
    # Catálogo conhecido (núcleo): nunca inventa skill inexistente no patch
    known = set()
    try:
        from hermes_cli.config import get_hermes_home as _gh

        agent_skills = Path(str(_gh())) / "hermes-agent" / "skills"
        if agent_skills.exists():
            known = {p.name for p in agent_skills.iterdir() if p.is_dir()}
    except Exception:
        pass
    unknown = [s for s in skills if s not in known] if known else []
    record = {
        "model": model,
        "skills": skills,
        "unknown": unknown,
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    out = _buffer_dir() / "skills-applied.json"
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    patch = {"skills": {"config": {s: True for s in skills if s not in unknown}}}
    return {
        "status": "ok",
        "path": str(out),
        "unknown": unknown,
        "suggested_config_patch": patch,
        "hint": "cole suggested_config_patch em config.yaml, ou ative via LAB",
    }


def health() -> dict:
    """Probe rápido: MCP ajuda, Ollama :11434, tamanho do buffer."""
    mcp = False
    try:
        from tools.registry import (
            registry,
        )  # import tardio p/ não quebrar teste isolado

        mcp = bool(getattr(registry, "_tools", {}))
    except Exception:
        mcp = False
    ollama = False
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
        with urllib.request.urlopen(req, timeout=2) as r:
            ollama = r.status == 200
    except Exception:
        ollama = False
    buf = _buffer_dir() / "prompt.md"
    return {
        "status": "ok",
        "mcp": mcp,
        "ollama": ollama,
        "buffer_bytes": buf.stat().st_size if buf.exists() else 0,
        "offline_ok": True,
    }
