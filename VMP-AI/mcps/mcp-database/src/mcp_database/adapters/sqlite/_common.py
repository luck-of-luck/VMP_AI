from __future__ import annotations


def _ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'
